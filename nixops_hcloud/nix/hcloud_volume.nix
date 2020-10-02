{ lib, uuid, name, ... }:
with lib;
{
  options = {
    inherit (import ./context.nix { inherit lib; }) token context;

    name = mkOption {
      default = "nixops-${uuid}-${name}";
      type = types.str;
      description = "Name of the Hetzner Cloud volume.";
    };

    size = mkOption {
      type = types.int;
      example = 10;
      description = "Size of volume, in Gb";
    };

    location = mkOption {
      type = types.str;
      example = "fsn1";
      description = "Volume location name";
    };
  };

  config._type = "hcloud-volume";
}
