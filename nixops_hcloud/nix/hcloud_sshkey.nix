{ config, lib, uuid, name, ... }:
with lib;
{
  options = {
    inherit (import ./context.nix { inherit lib; }) token context;

    name = mkOption {
      default = "nixops-${uuid}-${name}";
      type = types.str;
      description = "Name of the Hetzner Cloud SSH key.";
    };

    publicKey = mkOption {
      type = types.str;
      description = "SSH public key";
    };
  };

  config._type = "hcloud-sshkey";
}
