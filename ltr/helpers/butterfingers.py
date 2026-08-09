"""Typo generation using keyboard proximity.

This module provides functionality for generating realistic typos by simulating
keyboard proximity errors, where characters are replaced with nearby keys on
a QWERTY keyboard.
"""


def butterfingers(text: str, prob: float = 0.1, keyboard: str = "qwerty") -> str:
    """Generate typos in text by simulating keyboard proximity errors.

    Randomly replaces characters with nearby keys on a QWERTY keyboard to
    simulate realistic typing mistakes. Original case is preserved.

    Args:
        text: Input text string to add typos to.
        prob: Probability of introducing a typo for each character (default: 0.1).
        keyboard: Keyboard layout to use (default: "qwerty"). Other layouts
            are not currently supported.

    Returns:
        str: Text string with typos introduced based on keyboard proximity.

    Note:
        Implementation adapted from:
        https://github.com/Decagon/butter-fingers/blob/master/butterfingers/butterfingers.py
    """
    import random

    key_approx = {}

    if keyboard == "qwerty":
        key_approx["q"] = "qwasedzx"
        key_approx["w"] = "wqesadrfcx"
        key_approx["e"] = "ewrsfdqazxcvgt"
        key_approx["r"] = "retdgfwsxcvgt"
        key_approx["t"] = "tryfhgedcvbnju"
        key_approx["y"] = "ytugjhrfvbnji"
        key_approx["u"] = "uyihkjtgbnmlo"
        key_approx["i"] = "iuojlkyhnmlp"
        key_approx["o"] = "oipklujm"
        key_approx["p"] = "plo['ik"

        key_approx["a"] = "aqszwxwdce"
        key_approx["s"] = "swxadrfv"
        key_approx["d"] = "decsfaqgbv"
        key_approx["f"] = "fdgrvwsxyhn"
        key_approx["g"] = "gtbfhedcyjn"
        key_approx["h"] = "hyngjfrvkim"
        key_approx["j"] = "jhknugtblom"
        key_approx["k"] = "kjlinyhn"
        key_approx["l"] = "lokmpujn"

        key_approx["z"] = "zaxsvde"
        key_approx["x"] = "xzcsdbvfrewq"
        key_approx["c"] = "cxvdfzswergb"
        key_approx["v"] = "vcfbgxdertyn"
        key_approx["b"] = "bvnghcftyun"
        key_approx["n"] = "nbmhjvgtuik"
        key_approx["m"] = "mnkjloik"
        key_approx[" "] = " "
    else:
        print("Keyboard not supported.")

    prob_of_typo = int(prob * 100)

    buttertext = ""
    for letter in text:
        lcletter = letter.lower()
        if lcletter not in key_approx:
            newletter = lcletter
        else:
            if random.choice(range(0, 100)) <= prob_of_typo:
                newletter = random.choice(key_approx[lcletter])
            else:
                newletter = lcletter
        # go back to original case
        if lcletter != letter:
            newletter = newletter.upper()
        buttertext += newletter

    return buttertext
