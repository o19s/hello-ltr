def resp_msg(msg, resp, throw=True, ignore=[]):
    rsc = resp.status_code
    print(f"{msg} [Status: {rsc}]")
    if rsc >= 400 and rsc not in ignore and throw:
        raise RuntimeError(resp.text)
