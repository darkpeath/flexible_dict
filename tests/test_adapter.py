# -*- coding: utf-8 -*-

from typing import List, Optional, Union
import pytest
import flexible_dict as fd
from flexible_dict.adapter import (
    Encoder, Decoder, TypeAdapter,
    get_encoder_func, get_decoder_func,
    JsonObjectEncoder, JsonArrayEncoder,
    AdapterDetector,
)

@fd.json_object
class Inner:
    x: int = fd.Field(getter_default=0)

class UpperEncoder(Encoder):
    def encode(self, value):
        return value.upper()

class LowerDecoder(Decoder):
    def decode(self, value):
        return value.lower()

class AddOneAdapter(TypeAdapter):
    def cast(self, value):
        return value + 1

def test_get_encoder_func():
    assert get_encoder_func(UpperEncoder())("ab") == "AB"
    assert get_encoder_func(AddOneAdapter())(1) == 2
    assert get_encoder_func(int)("3") == 3
    with pytest.raises(ValueError):
        get_encoder_func(123)
    assert get_encoder_func(123, ignore_err=True) == 123

def test_get_decoder_func():
    assert get_decoder_func(LowerDecoder())("AB") == "ab"
    assert get_decoder_func(AddOneAdapter())(1) == 2
    assert get_decoder_func(str)(3) == "3"
    with pytest.raises(ValueError):
        get_decoder_func(123)
    assert get_decoder_func(123, ignore_err=True) == 123

def test_json_object_encoder():
    encoder = JsonObjectEncoder(Inner)
    encoded = encoder({'x': 1})
    assert type(encoded) is Inner
    assert encoded.x == 1
    # an Inner instance or a non-dict value is left unchanged
    inner = Inner({'x': 2})
    assert encoder(inner) is inner
    assert encoder(5) == 5

def test_json_array_encoder():
    encoder = JsonArrayEncoder(JsonObjectEncoder(Inner))
    encoded = encoder([{'x': 1}, {'x': 2}])
    assert [type(e) for e in encoded] == [Inner, Inner]
    assert encoder.encode(None) is None
    with pytest.raises(ValueError):
        encoder.encode("not a list")

def test_detect_encoder():
    detector = AdapterDetector()
    # no encoder needed for built-in types
    assert detector.detect_encoder(int) is None
    assert detector.detect_encoder(str) is None
    assert detector.detect_encoder(List[int]) is None
    # json object class and containers of it need encoders
    assert isinstance(detector.detect_encoder(Inner), JsonObjectEncoder)
    assert isinstance(detector.detect_encoder(List[Inner]), JsonArrayEncoder)
    assert isinstance(detector.detect_encoder(Optional[Inner]), JsonObjectEncoder)
    assert isinstance(detector.detect_encoder(Union[Inner, None]), JsonObjectEncoder)
    # union of multiple real types cannot be detected
    assert detector.detect_encoder(Union[Inner, int]) is None

def test_detect_decoder():
    # currently no decoder is auto detected
    assert AdapterDetector().detect_decoder(Inner) is None
