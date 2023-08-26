# -*- coding: utf-8 -*-

"""
encoder and decoder to convert value when write or read a dict key
"""

from typing import Any
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
