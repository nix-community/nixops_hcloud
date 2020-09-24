# Configuration specific to the Hetzner Cloud backend.
{ config, lib, ... }:
with lib;
{
  ###### interface

  options.deployment.hetznercloud = {
    inherit (import ./context.nix { inherit lib; }) token context;

    image = mkOption {
      type = types.nullOr types.int;
      default = null;
      description = ''
        Image ID to use for this VM. It's expected to be a NixOs system with SSH access to root.
        Takes precedence over <option>deployment.hetznercloud.image_selector</option>.
      '';
    };

    image_selector = mkOption {
      type = types.str;
      default = "nixops";
      description = ''
        <link xlink:href='https://docs.hetzner.cloud/#label-selector'>Label selector</link> for the
        server image. If multiple images are found, the most recent one will be used.
        The image is expected to be a NixOs system with SSH access to root.
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
  };

  ###### implementation

  config = mkIf (config.deployment.targetEnv == "hetznercloud") {
    nixpkgs.system = mkOverride 900 "x86_64-linux";

    # TODO where do imports go?
    # imports = [
    #   <nixpkgs/nixos/modules/profiles/qemu-guest.nix>
    # ];

    boot.initrd.availableKernelModules = [ "ata_piix" "virtio_pci" "xhci_pci" "sd_mod" "sr_mod" ];
    boot.initrd.kernelModules = [ ];
    boot.kernelModules = [ ];
    boot.extraModulePackages = [ ];
    boot.loader.grub.enable = true;
    boot.loader.grub.version = 2;
    system.stateVersion = "20.03";
    boot.loader.grub.devices = ["/dev/sda"];

    fileSystems."/" = { device = "/dev/sda"; fsType = "ext4"; };

    networking.interfaces.ens3.useDHCP = true;
    services.openssh.enable = true;
  };
}
