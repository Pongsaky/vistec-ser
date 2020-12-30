from tensorflow.keras import Model
from tensorflow.keras.regularizers import l2
import tensorflow as tf

from models.layers.cnn_blocks import *
from models.layers.rnn import *


class Wav2Letter(Model):
    def __init__(self, n_classes: int, activation: str = 'relu', **kwargs):
        super().__init__(**kwargs)
        self.activation = activation
        self.conv_layers = [
            self._get_CNN(250, 48, stride=2, activation=self.activation),
            self._get_CNN(250, 7, stride=1, activation=self.activation),
            self._get_CNN(250, 7, stride=1, activation=self.activation),
            self._get_CNN(250, 7, stride=1, activation=self.activation),
            self._get_CNN(250, 7, stride=1, activation=self.activation),
            self._get_CNN(250, 7, stride=1, activation=self.activation),
            self._get_CNN(250, 7, stride=1, activation=self.activation),
            self._get_CNN(250, 7, stride=1, activation=self.activation),
            self._get_CNN(2000, 32, stride=1, activation=self.activation),
            self._get_CNN(2000, 1, stride=1, activation=self.activation),
            self._get_CNN(n_classes, 1, stride=1, activation=self.activation),
        ]

    def _get_CNN(self, filters: int, kernel_size: int, stride: int = 1, activation: str = 'relu'):
        return tf.keras.Sequential([
            Conv1D(filters=filters, kernel_size=kernel_size, strides=stride, activation=activation),
            BatchNormalization()
        ])

    def call(self, x, training=False):
        for cnn in self.conv_layers:
            x = cnn(x, training=training)
        x = tf.reduce_mean(x, axis=1)
        x = tf.nn.softmax(x, axis=-1)
        return x


class CNN1DLSTM(Model):
    def __init__(
            self,
            n_classes: int,
            num_channels: List[int] = [64, 64, 128, 128],
            kernel_sizes: List[int] = [4, 3, 3, 3],
            pool_sizes: List[int] = [2, 2, 2, 2],
            strides: List[int] = [1, 1, 1, 1],
            padding: List[str] = ['same']*4,
            bidirectional: bool = True,
            rnn_units: List[int] = [128],
            norm_method: str = 'layer',
            dropout: float = 0.5,
            **kwargs):
        super().__init__(**kwargs)

        self.num_channels = num_channels
        self.kernel_sizes = kernel_sizes
        self.pool_sizes = pool_sizes
        self.bidirectional = bidirectional
        self.rnn_units = rnn_units
        self.n_classes = n_classes
        self.dropout = dropout

        # CNN layers
        assert len(num_channels) == len(kernel_sizes) == len(
            pool_sizes), 'Number of channel / kernel / pool sizes mismatch: {}, {} and {}'.format(len(num_channels),
                                                                                                  len(kernel_sizes),
                                                                                                  len(pool_sizes))
        self.cnn_layers = [CNN1DBlock(
            n_channel=c,
            kernel_size=k,
            pool_size=p,
            norm_method=norm_method
        ) for c, k, p in zip(num_channels, kernel_sizes, pool_sizes)]

        # RNN layer
        self.recurrent_layers = [LSTM(unit, return_sequences=True) if i != len(rnn_units)-1 else LSTM(unit) for i, unit in enumerate(rnn_units)]
        if bidirectional:
            self.recurrent_layers = [Bidirectional(layer) for layer in self.recurrent_layers]
        # logits layer
        self.logits = Dense(n_classes)

    def get_config(self):
        return {'num_channels': self.num_channels,
                'kernel_sizes': self.kernel_sizes,
                'pool_sizes': self.pool_sizes,
                'bidirectional': self.bidirectional,
                'rnn_units': self.rnn_units,
                'n_classes': self.n_classes,
                'dropout': self.dropout}

    def call(self, x, training=False) -> tf.Tensor:
        # cnn layers
        for cnn_block in self.cnn_layers:
            x = cnn_block(x, training=training)

        # masking
        x = Masking()(x)

        # lstm
        for rnn in self.recurrent_layers:
            x = rnn(x)

        # dense
        if training:
            x = tf.nn.dropout(x, rate=self.dropout)
        x = self.logits(x)
        return tf.nn.softmax(x, axis=-1)