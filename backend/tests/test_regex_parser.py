"""Test the regex parser against example messages from the spec."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.parser.regex_parser import parse_message, parse_message_to_offers


def test_spec_examples():
    """Test all example messages from the specification."""
    test_cases = [
        {
            "input": "15 Pro Max 256 nat - 915$",
            "expected_model": "iPhone 15 Pro Max",
            "expected_memory": "256GB",
            "expected_color": "Natural Titanium",
            "expected_price": 915.0,
            "expected_currency": "USD",
        },
        {
            "input": "iPhone 15 PM 256 Natural 91 500",
            "expected_model": "iPhone 15 Pro Max",
            "expected_memory": "256GB",
            "expected_color": "Natural Titanium",
            "expected_price": 91500.0,
            "expected_currency": "RUB",
        },
        {
            "input": "Apple 15 ProMax / 256 / white / new / 920 usd",
            "expected_model": "iPhone 15 Pro Max",
            "expected_memory": "256GB",
            "expected_color": "White",
            "expected_price": 920.0,
            "expected_currency": "USD",
        },
        {
            "input": "16/256 black esim 101000",
            "expected_model": "iPhone 16",
            "expected_memory": "256GB",
            "expected_color": "Black",
            "expected_price": 101000.0,
            "expected_currency": "RUB",
        },
        {
            "input": "AirPods Pro 2 USB-C 14500",
            "expected_model": "AirPods Pro 2 USB-C",
            "expected_memory": None,
            "expected_price": 14500.0,
            "expected_currency": "RUB",
        },
    ]

    all_passed = True
    for i, tc in enumerate(test_cases):
        print(f"\n--- Test {i+1}: {tc['input']!r} ---")
        result = parse_message(tc["input"])

        if not result.offers:
            print(f"  FAIL: No offers parsed!")
            all_passed = False
            continue

        offer = result.offers[0]
        print(f"  Model:    {offer.model} (expected: {tc['expected_model']})")
        print(f"  Memory:   {offer.memory} (expected: {tc.get('expected_memory')})")
        print(f"  Color:    {offer.color} (expected: {tc.get('expected_color')})")
        print(f"  Price:    {offer.price} (expected: {tc['expected_price']})")
        print(f"  Currency: {offer.currency} (expected: {tc['expected_currency']})")
        print(f"  Confidence: {offer.confidence}")
        print(f"  SIM type: {offer.sim_type}")
        print(f"  Condition: {offer.condition}")

        errors = []
        if offer.model != tc["expected_model"]:
            errors.append(f"model: got {offer.model!r}, expected {tc['expected_model']!r}")
        if tc.get("expected_memory") and offer.memory != tc["expected_memory"]:
            errors.append(f"memory: got {offer.memory!r}, expected {tc['expected_memory']!r}")
        if tc.get("expected_color") and offer.color != tc.get("expected_color"):
            errors.append(f"color: got {offer.color!r}, expected {tc['expected_color']!r}")
        if offer.price != tc["expected_price"]:
            errors.append(f"price: got {offer.price}, expected {tc['expected_price']}")
        if offer.currency != tc["expected_currency"]:
            errors.append(f"currency: got {offer.currency!r}, expected {tc['expected_currency']!r}")

        if errors:
            print(f"  ERRORS: {'; '.join(errors)}")
            all_passed = False
        else:
            print(f"  PASS")

    print(f"\n{'='*50}")
    if all_passed:
        print("ALL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED - see above")
    return all_passed


def test_multi_line():
    """Test multi-line message parsing."""
    text = """iPhone 15 Pro Max 256 Natural 92000
iPhone 15 Pro 128 Blue 78000
AirPods Pro 2 USB-C 14500
Apple Watch Ultra 2 52000"""

    print("\n--- Multi-line test ---")
    result = parse_message(text)
    print(f"  Parsed {len(result.offers)} offers, {len(result.unparsed_lines)} unparsed")
    for offer in result.offers:
        print(f"  - {offer.model} {offer.memory or ''} {offer.color or ''} = {offer.price} {offer.currency} (conf={offer.confidence})")

    assert len(result.offers) >= 3, f"Expected >=3 offers, got {len(result.offers)}"
    print("  PASS")


def test_additional_formats():
    """Test additional common formats."""
    cases = [
        ("iPhone 16 Pro Max 512 Black Titanium 125000", "iPhone 16 Pro Max", "512GB"),
        ("16pm 256 dt esim 115000", "iPhone 16 Pro Max", "256GB"),
        ("14 Pro 128 purple 65000", "iPhone 14 Pro", "128GB"),
        ("13 mini 128 white 45000", "iPhone 13 Mini", "128GB"),
        ("iPad Pro 13 256 85000", "iPad Pro 13", "256GB"),
        ("MacBook Air 15 512 135000", "MacBook Air 15", "512GB"),
    ]

    print("\n--- Additional format tests ---")
    all_ok = True
    for text, expected_model, expected_mem in cases:
        result = parse_message(text)
        if not result.offers:
            print(f"  FAIL: '{text}' -> no offers")
            all_ok = False
            continue
        offer = result.offers[0]
        ok = offer.model == expected_model and offer.memory == expected_mem
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_ok = False
        print(f"  {status}: '{text}' -> {offer.model} {offer.memory} = {offer.price}")

    return all_ok


if __name__ == "__main__":
    p1 = test_spec_examples()
    test_multi_line()
    p3 = test_additional_formats()

    if p1 and p3:
        print("\n ALL TESTS PASSED!")
    else:
        print("\n SOME TESTS FAILED")
        sys.exit(1)
