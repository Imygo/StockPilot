import torch
from torch import nn


class CNNLSTM(nn.Module):
    def __init__(self, n_features=4):
        super().__init__()
        self.conv = nn.Sequential(nn.Conv1d(n_features, 32, 3, padding=1), nn.ReLU())
        self.lstm = nn.LSTM(32, 32, batch_first=True)
        self.head = nn.Linear(32, 1)

    def forward(self, x):
        x = self.conv(x.transpose(1,2)).transpose(1,2)
        x, _ = self.lstm(x)
        return self.head(x[:,-1]).squeeze(-1)
