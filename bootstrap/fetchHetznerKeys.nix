{ config, lib, pkgs, ... }:
let script = pkgs.writeShellScript "fetch-hetzner-keys.sh"
  ''
  #!/bin/bash
  umask 077
  mkdir -p /root/.ssh
  URL="http://169.254.169.254/hetzner/v1"
  for ENDPOINT in metadata userdata; do
    ${pkgs.curl}/bin/curl -q "$URL/$ENDPOINT" \
      | ${pkgs.yq}/bin/yq '.["public-keys"] // [] | join("\n")' \
      -r >> /root/.ssh/authorized_keys.new
  done
  mv /root/.ssh/authorized_keys.new /root/.ssh/authorized_keys
  '';
in
{
  options = with lib; {
    fetchHetznerKeys.enable = mkEnableOption "fetch-hetzner-keys";
  };

  config = {
    systemd.services = lib.attrsets.optionalAttrs config.fetchHetznerKeys.enable {
      fetch-hetzner-keys = {
        description = "Fetches SSH keys from hetzner instance metadata.";
        wantedBy = [ "multi-user.target" ];

        serviceConfig = {
          type = "oneshot";
          user = "root";
          ExecStart = script;
        };
      };
    };
  };
}
