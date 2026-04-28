from sportorg.modules.trailo.codes import expand_trailo_control_code_strings


def test_expand_inserts_1TT_before_1T1A_when_missing() -> None:
    codes = [
        "1A",
        "1T1A",
        "1T2B",
        "1T3C",
    ]
    exp = expand_trailo_control_code_strings(codes)
    assert exp == ["1A", "1TT", "1T1A", "1T2B", "1T3C"]


def test_expand_noop_when_1TT_present() -> None:
    codes = ["1TT", "1T1A", "1T2B"]
    assert expand_trailo_control_code_strings(codes) == codes


def test_expand_legacy_inserts_110TT_before_111TA() -> None:
    codes = ["110TT", "111TA"]
    assert expand_trailo_control_code_strings(codes) == codes
    codes2 = ["111TA", "112TB"]
    exp = expand_trailo_control_code_strings(codes2)
    assert exp[0] == "110TT"
    assert "111TA" in exp and "112TB" in exp
