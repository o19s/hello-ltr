"""Typo generation using keyboard proximity.

This module provides functionality for generating realistic typos by simulating
keyboard proximity errors, where characters are replaced with nearby keys on
a QWERTY keyboard.
"""


def butterfingers(text, prob=0.1, keyboard="qwerty"):
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

    keyApprox = {}

    if keyboard == "qwerty":
        keyApprox["q"] = "qwasedzx"
        keyApprox["w"] = "wqesadrfcx"
        keyApprox["e"] = "ewrsfdqazxcvgt"
        keyApprox["r"] = "retdgfwsxcvgt"
        keyApprox["t"] = "tryfhgedcvbnju"
        keyApprox["y"] = "ytugjhrfvbnji"
        keyApprox["u"] = "uyihkjtgbnmlo"
        keyApprox["i"] = "iuojlkyhnmlp"
        keyApprox["o"] = "oipklujm"
        keyApprox["p"] = "plo['ik"

        keyApprox["a"] = "aqszwxwdce"
        keyApprox["s"] = "swxadrfv"
        keyApprox["d"] = "decsfaqgbv"
        keyApprox["f"] = "fdgrvwsxyhn"
        keyApprox["g"] = "gtbfhedcyjn"
        keyApprox["h"] = "hyngjfrvkim"
        keyApprox["j"] = "jhknugtblom"
        keyApprox["k"] = "kjlinyhn"
        keyApprox["l"] = "lokmpujn"

        keyApprox["z"] = "zaxsvde"
        keyApprox["x"] = "xzcsdbvfrewq"
        keyApprox["c"] = "cxvdfzswergb"
        keyApprox["v"] = "vcfbgxdertyn"
        keyApprox["b"] = "bvnghcftyun"
        keyApprox["n"] = "nbmhjvgtuik"
        keyApprox["m"] = "mnkjloik"
        keyApprox[" "] = " "
    else:
        print("Keyboard not supported.")

    probOfTypo = int(prob * 100)

    buttertext = ""
    for letter in text:
        lcletter = letter.lower()
        if lcletter not in keyApprox:
            newletter = lcletter
        else:
            if random.choice(range(0, 100)) <= probOfTypo:
                newletter = random.choice(keyApprox[lcletter])
            else:
                newletter = lcletter
        # go back to original case
        if lcletter != letter:
            newletter = newletter.upper()
        buttertext += newletter

    return buttertext
