def resp_msg(msg, resp, throw=True, ignore=[]):
    rsc = resp.status_code
    print('{} [Status: {}]'.format(msg, rsc))
    if rsc >= 400 and rsc not in ignore:
        if throw:
            raise RuntimeError(resp.text)

