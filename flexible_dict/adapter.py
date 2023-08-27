# -*- coding: utf-8 -*-

"""
encoder and decoder to convert value when write or read a dict key
"""

from typing import (
    Any, List, Optional,
    Union, Callable,
)
from abc import abstractmethod, ABC
import dataclasses

class TypeAdapter(ABC):
    """
    an abstract class representing an encoder or decoder to convert the value type
    """
    @abstractmethod
    def cast(self, value: Any) -> Any:
        pass
    def __call__(self, value: Any) -> Any:
        return self.cast(value)

class Encoder(TypeAdapter, ABC):
    """
    an abstract encoder
    """
    @abstractmethod
    def encode(self, value: Any) -> Any:
        pass
    def cast(self, value: Any) -> Any:
        return self.encode(value)

class Decoder(TypeAdapter, ABC):
    """
    an abstract decoder
    """
    @abstractmethod
    def decode(self, value: Any) -> Any:
        pass
    def cast(self, value: Any) -> Any:
        return self.decode(value)

_ENCODER_TYPE = Union[Encoder, TypeAdapter, Callable[[Any], Any]]
_DECODER_TYPE = Union[Decoder, TypeAdapter, Callable[[Any], Any]]

def get_encoder_func(encoder: _ENCODER_TYPE, ignore_err=False) -> Callable[[Any], Any]:
    """
    get actual encode function for the given encoder
    :param encoder:         can be a function or an instance of `Encoder` or `TypeAdapter`
    :param ignore_err:      if `False`, raise an exception if encoder type is unexpected;
                            else return the encoder unchanged
    :return:    an encode function if no error occurs
    """
    if isinstance(encoder, Encoder):
        return encoder.encode
    if isinstance(encoder, TypeAdapter):
        return encoder.cast
    if callable(encoder):
        return encoder
    if ignore_err:
        return encoder
    raise ValueError(f"unexpected encoder type: {type(encoder)}")

def get_decoder_func(decoder: _DECODER_TYPE, ignore_err=False) -> Callable[[Any], Any]:
    """
    get actual decode function for the given decoder
    :param decoder:         can be a function or an instance of `Decoder` or `TypeAdapter`
    :param ignore_err:      if `False`, raise an exception if decoder type is unexpected;
                            else return the decoder unchanged
    :return:    a decode function if no error occurs
    """
    if isinstance(decoder, Decoder):
        return decoder.decode
    if isinstance(decoder, TypeAdapter):
        return decoder.cast
    if callable(decoder):
        return decoder
    if ignore_err:
        return decoder
    raise ValueError(f"unexpected decoder type: {type(decoder)}")

@dataclasses.dataclass
class JsonObjectEncoder(Encoder):
    """
    a json object encoder, to cast dict value as a json object
    """
    type: type
    def encode(self, value: Any) -> Any:
        if not isinstance(value, self.type) and isinstance(value, dict):
            return self.type(value)
        return value

@dataclasses.dataclass
class JsonArrayEncoder(Encoder):
    """
    a json array encoder, to cast list value as List[json_object_class]
    """
    elem_encoder: _ENCODER_TYPE   # an encoder for list element, this arg must be set not `None`

    def __post_init__(self):
        self.elem_encoder = get_encoder_func(self.elem_encoder)

    def encode(self, value: Optional[List[Any]]) -> Optional[List[Any]]:
        if value is None:
            return value
        if not isinstance(value, list):
            raise ValueError("value is not a list")
        return [self.elem_encoder(x) for x in value]


class AdapterDetector:
    """
    auto detect encoder and decoder for given type
    """
    def detect_encoder(self, a_type: type) -> Optional[Encoder]:
        if isinstance(a_type, type) and hasattr(a_type, '__json_object_fields__'):
            return JsonObjectEncoder(a_type)
        return None
    @staticmethod
    def detect_decoder(a_type: type) -> Optional[Decoder]:
        # currently, no type value is to be decoded when read from dict
        # user can rewrite this method for custom use
        return None

