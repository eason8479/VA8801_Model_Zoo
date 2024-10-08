#import warnings
#warnings.simplefilter('ignore', UserWarning)
import os, sys
from pathlib import Path
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torch.nn.utils.rnn import pad_sequence
from data import AudioData
import hydra
from omegaconf import OmegaConf,open_dict, listconfig
from network import SED
from tools import LossWriter
from utils import Trainer
import json

NUM_LABEL = 4

def collate_fn(sample):
    '''
    batch: [sample, sample, ...]
    '''
    feats_length = torch.tensor([ x['feat'].size(0) for x in sample], dtype=torch.int32)
    order = torch.argsort(feats_length, descending=True)

    feats_lengths = torch.tensor([sample[i]['feat'].size(0) for i in order], dtype=torch.int32)
    sorted_feats = [sample[i]['feat'] for i in order]
    sorted_keys = [sample[i]['key'] for i in order]
    padded_feats = pad_sequence(sorted_feats, batch_first=True, padding_value=0)
    #
    #padded_labels = torch.tensor([sample[i]['label'] for i in order], dtype=torch.int32)
    padded_labels = torch.tensor([sample[i]['label'] for i in order]).long()
    #label_lengths = torch.tensor([1 for i in order], dtype=torch.int32)
    label_lengths = torch.ones(len(sample), dtype=torch.int32)
    return (sorted_keys, padded_feats, padded_labels, feats_lengths, label_lengths)

@hydra.main(version_base=None, config_path='conf', config_name='config')
def main(args):
    args.ckpt = os.path.join(args.ckpt_dir, args.ckpt_name)
    #
    net = SED(NUM_LABEL, args.fft.n_mel, pooling_type='TAP')
    num_params = sum(p.numel() for p in net.parameters() if p.requires_grad)
    print(f"# of NN parameters: {num_params}")
    net.load_state_dict( torch.load(args.pretrain.ckpt, map_location='cpu')['model'])
    for param in net.parameters():
        param.requires_grad = False
    net.fc = nn.Linear(64, args.num_label)

    net.to(args.device)

    
    print("training data processing")
    tr_data = AudioData(args.tr, args, args.dry_run)
    print("validation data processing")
    cv_data = AudioData(args.cv, args, args.dry_run, is_tr=False)
    #
    tr_loader = DataLoader(tr_data, batch_size=args.batch_size, shuffle=True, num_workers=args.num_workers, pin_memory=True, drop_last=False,
            collate_fn=collate_fn)
    cv_loader = DataLoader(cv_data, batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers, pin_memory=True, drop_last=False,
            collate_fn=collate_fn)
    print("# of tr_loader: ", len(tr_loader))
    print("# of cv_loader: ", len(cv_loader))
    loader = {"tr_loader": tr_loader,
            "cv_loader": cv_loader,
            }

    # optimizer
    optimizer = torch.optim.Adam(net.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.85, patience=args.lr_patience)

    # objective function
    criterion = nn.CrossEntropyLoss()

    logdir = Path(args.ckpt)/'log'
    logdir.mkdir(parents=True, exist_ok=True)
    writer = LossWriter(logdir)

    #
    config = OmegaConf.to_container(args, throw_on_missing=False)
    path = Path(args.ckpt)/"training_config.json".format(args.ckpt_name)
    with open(path, 'w') as f:
        json.dump(config, f)

    trainer = Trainer(net, criterion, loader, optimizer, scheduler, writer, args)
    trainer.train()

if __name__ == "__main__":
    main()

