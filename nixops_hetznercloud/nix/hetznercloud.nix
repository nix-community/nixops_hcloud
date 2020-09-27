# Configuration specific to the Hetzner Cloud backend.
{ config, pkgs, lib, ... }:
with lib;
{
  ###### interface

  options.deployment.hetznercloud = {
    inherit (import ./context.nix { inherit lib; }) token context;

    image = mkOption {
      type = types.nullOr types.int;
      default = null;
      description = ''
        Image ID to use for this VM. It's expected to be a NixOs system with fetchHetznerKeys enabled.
        Takes precedence over <option>deployment.hetznercloud.image_selector</option>.
      '';
    };

    image_selector = mkOption {
      type = types.str;
      default = "nixops";
      description = ''
        <link xlink:href='https://docs.hetzner.cloud/#label-selector'>Label selector</link> for the
        server image. If multiple images are found, the most recent one will be used.
        The image is expected to be a NixOs system with fetchHetznerKeys enabled.
      '';
    };

    location = mkOption {
      type = types.str;
      example = "fsn1";
      description = ''
        VM location name.
      '';
    };

    serverType = mkOption {
      type = types.str;
      example = "cx11";
      description = ''
        Hetzner Cloud server type name.
      '';
    };

    upgradeDisk = mkOption {
      type = types.bool;
      default = false;
      description = ''
        Whether to upgrade the disk when upgrading the server type.
        If true the server can't be downscaled back.
      '';
    };
  };

  ###### implementation

  config = mkIf (config.deployment.targetEnv == "hetznercloud") {
    nixpkgs.system = mkOverride 900 "x86_64-linux";

    boot.loader.grub.enable = true;
    boot.loader.grub.version = 2;
    system.stateVersion = "20.03";
    boot.loader.grub.devices = ["/dev/sda"];

    networking.interfaces.ens3.useDHCP = true;
    services.openssh.enable = true;
  };
}
