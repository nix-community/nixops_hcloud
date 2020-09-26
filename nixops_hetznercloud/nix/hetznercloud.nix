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

    systemd.services.fetch-hetzner-keys = {
      description = "Fetches SSH keys from hetzner instance metadata.";
      wantedBy = [ "multi-user.target" ];

      serviceConfig =
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
      in {
        type = "oneshot";
        user = "root";
        ExecStart = script;
      };
    };
  };
}
