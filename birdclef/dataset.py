# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/02_dataset.ipynb.

# %% auto 0
__all__ = ['dir', 'simple_classes', 'train_metadata_simple', 'val_metadata_simple', 'test_metadata_simple', 'dataset_dict',
           'MyPipeline', 'BirdClef', 'get_dataset', 'get_dataloader']

# %% ../nbs/02_dataset.ipynb 3
from IPython.display import Audio
import pandas as pd
from sklearn.preprocessing import LabelBinarizer

import torch
from torch.utils.data import Dataset, DataLoader
import torchaudio

from .utils import DATA_DIR, AUDIO_DATA_DIR, mel_to_wave, plot_audio, plot_spectrogram

# %% ../nbs/02_dataset.ipynb 7
# Define custom feature extraction pipeline.
#
# 1. Check for sample rate and resample
# 2. Waveform Augmenations
# 3. Convert to mel-scale
# 4. Mel Augmenations
# 5. Check for lenght and stretch shorter videos


class MyPipeline(torch.nn.Module):
    def __init__(
        self,
        seconds = 5,
        sample_rate=32000,
        f_min = 50,
        f_max = 16000,
        n_fft=2048,
        n_mels=128,
        hop_length = 1024,
        power = 8.0
    ):
        super().__init__()

        self.n_fft = n_fft
        self.seconds = seconds
        self.c_length = seconds * sample_rate // hop_length + 1
        # self.c_length = c_length * 62.6 #626 sono 10 secondi
        self.sample_rate = sample_rate
        self.melspec = torchaudio.transforms.MelSpectrogram(sample_rate=self.sample_rate, n_fft=n_fft, hop_length=hop_length, n_mels=n_mels, f_min=f_min, f_max=f_max, power=power)
        self.amptodb = torchaudio.transforms.AmplitudeToDB()
        self.stretch = torchaudio.transforms.TimeStretch(hop_length=hop_length, n_freq=128)

        #Augmentations
        # self.maskingFreq =  torchaudio.transforms.FrequencyMasking(freq_mask_param=30)
        # self.maskingTime = torchaudio.transforms.TimeMasking(time_mask_param=30)
        # self.noiser = torchaudio.transforms.AddNoise()
        # self.pitchShift = torchaudio.transforms.PitchShift(resample_freq, 4)


    def forward(self, filename):
        # 0 Load the File
        waveform, sample_rate = torchaudio.load(filename, frame_offset=0, num_frames=self.seconds*self.sample_rate)
        
        # 1 Check for the sample rate and eventually resample to 32k
        if sample_rate != self.sample_rate:
           print("Wrong sample rate: resampling audio")
           resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=self.sample_rate)
           waveform = resampler(waveform)

        # 2 Noise gating
        # threshold_linear = waveform.std()
        # window_size = 2000
        # # Pad the waveform to ensure the envelope has the same length
        # padding = (window_size) // 2 
        # padded_waveform = torch.nn.functional.pad(waveform.unsqueeze(0), (padding, padding), 'constant', value=0).squeeze(0)

        # # Calculate the envelope using a moving average filter
        # envelope = torch.nn.functional.avg_pool1d(padded_waveform.abs().unsqueeze(0), kernel_size=window_size, stride=1).squeeze(0)
        # envelope = envelope[:, :waveform.shape[1]]

        # # Create a binary mask based on the energy and threshold
        # gate_mask = envelope >= threshold_linear

        # # Apply the gating mask to the waveform
        # gated_waveform = waveform.clone()
        # gated_waveform[~gate_mask] *= 0.1

        # 3 Convert to mel-scale
        mel = self.melspec(waveform)
        mel = self.amptodb(mel)
     
        # 4 Check for the length and stretch it to 10s, it is a transformation used to regularize the length of the data
        if mel.shape[2] < self.c_length:
        #   print("Audio too short: stretching it.")
          replay_rate =  mel.shape[2]/self.c_length
          #print(f"replay rate {replay_rate}%")
          mel = self.stretch(mel, replay_rate)
          mel = mel[:,:,0:self.c_length]
          #print(f"stretched shape {stretched.shape}")

        return mel.float()
    
    def inverse_transform(self, mel):
        n_stft = self.n_fft // 2 + 1
        mel = mel.cpu()
        mel = mel[:,:,0:self.c_length]
        print(mel.shape)
        invers_transform = torchaudio.transforms.InverseMelScale(sample_rate=self.sample_rate, n_stft=n_stft)
        grifflim_transform = torchaudio.transforms.GriffinLim(n_fft=self.n_fft)

        mel = torch.pow(10, mel/10)
        inverse_waveform = invers_transform(mel)
        pseudo_waveform = grifflim_transform(inverse_waveform)

        return pseudo_waveform

# %% ../nbs/02_dataset.ipynb 12
class BirdClef(Dataset):

    def __init__(self, metadata=None, classes=None):

        self.metadata = metadata
        self.classes = classes

        self.length = len(self.metadata)

        binarizer = LabelBinarizer()
        binarizer.fit(self.classes)

        self.labels = binarizer.transform(metadata.primary_label)
        
        self.num_classes = self.labels.shape[1]

        self.labels = torch.from_numpy(self.labels).float()
        
        _, self.labels = torch.max(self.labels, dim=1)
        
        # Initialize a pipeline
        self.pipeline = MyPipeline()
    
    def __len__(self):
        return self.length

    def __getitem__(self, idx):
        filename = AUDIO_DATA_DIR + self.metadata['filename'][idx]
        mel_spectrogram = self.pipeline(filename)

        label = self.labels[idx].long()
        
        return {'input': mel_spectrogram, 'label': label, 'filename': filename}

# %% ../nbs/02_dataset.ipynb 16
dir = DATA_DIR
try:
    train_metadata_base = pd.read_csv(dir + 'base/train_metadata.csv')
    val_metadata_base = pd.read_csv(dir + 'base/val_metadata.csv')
    test_metadata_base = pd.read_csv(dir + 'base/test_metadata.csv')
except FileNotFoundError:
    dir = 'data/'
    train_metadata_base = pd.read_csv(dir + 'base/train_metadata.csv')
    val_metadata_base = pd.read_csv(dir + 'base/val_metadata.csv')
    test_metadata_base = pd.read_csv(dir + 'base/test_metadata.csv')

simple_classes = ['thrnig1', 'wlwwar', 'barswa']
train_metadata_simple = train_metadata_base.loc[train_metadata_base.primary_label.isin(simple_classes)].reset_index()
val_metadata_simple = val_metadata_base.loc[val_metadata_base.primary_label.isin(simple_classes)].reset_index()
test_metadata_simple = test_metadata_base.loc[test_metadata_base.primary_label.isin(simple_classes)].reset_index()

# %% ../nbs/02_dataset.ipynb 17
dataset_dict = {
            'train_base': (BirdClef, {'metadata': train_metadata_base, 'classes': train_metadata_base.primary_label}),
            'val_base': (BirdClef, {'metadata': val_metadata_base, 'classes': train_metadata_base.primary_label}),
            'test_base': (BirdClef, {'metadata': test_metadata_base, 'classes': train_metadata_base.primary_label}),

            'train_simple': (BirdClef, {'metadata': train_metadata_simple, 'classes': train_metadata_simple.primary_label}),
            'val_simple': (BirdClef, {'metadata': val_metadata_simple, 'classes': train_metadata_simple.primary_label}),
            'test_simple': (BirdClef, {'metadata': test_metadata_simple, 'classes': train_metadata_simple.primary_label})
        }

# %% ../nbs/02_dataset.ipynb 18
def get_dataset(dataset_key:str        # A key of the dataset dictionary
                )->Dataset:         # Pytorch dataset
    "A getter method to retrieve the wanted dataset."
    assert dataset_key in dataset_dict, f'{dataset_key} is not an existing dataset, choose one from {dataset_dict.keys()}.'
    ds_class, kwargs = dataset_dict[dataset_key]
    return ds_class(**kwargs)

# %% ../nbs/02_dataset.ipynb 22
def get_dataloader(dataset_key:str,            # The key to access the dataset
                dataloader_kwargs:dict={}      # The optional parameters for a pytorch dataloader
                )->DataLoader:              # Pytorch dataloader
    "A function to get a dataloader from a specific dataset"
    dataset = get_dataset(dataset_key)

    return DataLoader(dataset, **dataloader_kwargs)
