{ config, pkgs, ... }:
{
  imports =
    [ ./hardware-configuration.nix
      ./fetchHetznerKeys.nix
    ];

  boot.loader.grub.enable = true;
  boot.loader.grub.version = 2;
  boot.loader.grub.devices = [ "/dev/sda" ];

  networking.useDHCP = false;
  networking.interfaces.ens3.useDHCP = true;

  services.openssh.permitRootLogin = "prohibit-password";
  services.openssh.enable = true;
  fetchHetznerKeys.enable = true;
}
