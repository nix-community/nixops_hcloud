# Configuration specific to the Hetzner Cloud backend.
{ config, pkgs, lib, ... }:
with lib;
with import ./lib.nix lib;
{
  ###### interface

  options.deployment.hcloud = {
    inherit (import ./context.nix { inherit lib; }) token context;

    image = mkOption {
      type = types.nullOr types.int;
      default = null;
      description = ''
        Image ID to use for this VM. It's expected to be a NixOs system with fetchHetznerKeys enabled.
        Takes precedence over <option>deployment.hcloud.image_selector</option>.
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

    sshKeys = mkOption {
      type = types.listOf (types.either types.string (resource "hcloud-sshkey"));
      default = [];
      description = ''
        List of SSH keys with root access to the machine. These will be managed with the fetch-hetzner-keys service, not by NixOS.
      '';
    };

    volumes =
      let volumeType = types.submodule {
        options = {
          volume = mkOption {
            type = types.either types.string (resource "hcloud-volume");
            description = ''
              Volume name or instance.
            '';
          };

          mountPoint = mkOption {
            type = types.nullOr types.string;
            default = null;
            description = ''
              Mount point for this volume. Won't be automounted when <literal>null</literal>.
            '';
          };

          fileSystem = mkOption {
            type = types.attrs;
            default = {};
            description = ''
              Options to be forwarded to <option>fileSystems.mountPoint</option>.
            '';
          };
        };
      };
      in mkOption {
        type = types.listOf volumeType;
        default = [];
        description = ''
          List of volumes attached to the machine.
        '';
      };
  };

  ###### implementation

  config = mkIf (config.deployment.targetEnv == "hcloud") {
    nixpkgs.system = mkOverride 900 "x86_64-linux";

    boot.loader.grub.enable = true;
    boot.loader.grub.version = 2;
    system.stateVersion = "20.03";
    boot.loader.grub.devices = ["/dev/sda"];

    networking.interfaces.ens3.useDHCP = true;
    services.openssh.enable = true;
  };
}
