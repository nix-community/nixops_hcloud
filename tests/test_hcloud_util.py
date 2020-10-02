from nixops_hcloud.hcloud_util import (HcloudConfig, HcloudContextOptions,
                                       get_access_token)


def test_get_access_token_precedence():
    # context > token > HCLOUD_CONTEXT > HCLOUD_TOKEN > default
    opt = HcloudContextOptions(context="opt_ctx", token="opt_token")
    env = {
        "HCLOUD_CONTEXT": "env_ctx",
        "HCLOUD_TOKEN": "env_token",
    }
    cfg = HcloudConfig(
        active_context="active",
        contexts={
            "active": "active_token",
            "env_ctx": "env_ctx_token",
            "opt_ctx": "opt_ctx_token",
        },
    )
    assert get_access_token(opt, env, cfg) == "opt_ctx_token"
    opt = HcloudContextOptions(context=None, token="opt_token")
    assert get_access_token(opt, env, cfg) == "opt_token"
    opt = HcloudContextOptions(context=None, token=None)
    assert get_access_token(opt, env, cfg) == "env_ctx_token"
    del env["HCLOUD_CONTEXT"]
    assert get_access_token(opt, env, cfg) == "env_token"
    del env["HCLOUD_TOKEN"]
    assert get_access_token(opt, env, cfg) == "active_token"
