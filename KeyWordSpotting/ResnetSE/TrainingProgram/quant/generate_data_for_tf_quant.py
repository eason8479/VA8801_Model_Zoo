import os, sys
from pathlib import Path
import torchaudio as ta
import torchaudio.functional as F
import pickle
import torch
from torch.nn.utils.rnn import pad_sequence
import numpy as np
import torchaudio.compliance.kaldi as kaldi


if len(sys.argv) < 2:
    print(f"Usage: {__file__} [path to save out data(*.npy)]")
    sys.exit(1)
src_tr = Path('../dataset/tr')
src_cv = Path('../dataset/cv')
out = sys.argv[1]
SR = 8000
n_mel = 24 

mels = []
wavs = []
wavs.extend(src_tr.glob('**/*.wav'))
wavs.extend(src_cv.glob('**/*.wav'))
print("# of files: ", len(wavs))

for w in wavs:
    s, sr = ta.load(w)
    if sr != SR:
        s = F.resample(s, orig_freq=sr, new_freq=SR)
    mel = kaldi.fbank(
            s, frame_length=25, frame_shift=10,
             num_mel_bins=n_mel, sample_frequency=SR)
    mel = mel - mel.mean(dim=0, keepdims=True) # mel: [T, n_mel]
    # T should be 192
    if mel.size(0) > 192:
        mel = mel[:192]
    mels.append(mel)

mels = pad_sequence(mels, batch_first=True)
# [batch_size, T, n_mel]
l = 192  - mels.size(1)
mels = torch.nn.functional.pad(mels,(0,0,0,l))
#
mels = mels.numpy()
np.save(out, mels)
