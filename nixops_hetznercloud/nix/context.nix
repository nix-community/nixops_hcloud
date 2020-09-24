{ lib, ... }:
with lib;
{
    # TODO make token/context precedence clearer:
    # cfg.context > cfg.token > HCLOUD_CONTEXT > HCLOUD_TOKEN > current context
    token = mkOption {
      default = null;
      type = types.nullOr types.str;
      description = ''
        Hetzner Cloud API token.

        If left empty, the value of the environment variable <envar>HCLOUD_TOKEN</envar> is used
        instead.
        When explicitly set, takes precedence over <envar>HCLOUD_CONTEXT</envar>.
      '';
    };

    context = mkOption {
      default = null;
      type = types.nullOr types.str;
      description = ''
        <link xlink:href="https://github.com/hetznercloud/cli">hcloud</link> context to use.

        If left empty, the value of the environment variable <envar>HCLOUD_CONTEXT</envar> is used
        if present, else the current active context is used.
        Takes precedence over <option>deployment.hetznercloud.token</option> if explicitly set.
      '';
    };
}
