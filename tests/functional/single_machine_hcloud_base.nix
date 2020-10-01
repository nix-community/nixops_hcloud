{
  network = {};

  resources.hetznercloudSshKeys.test-key = {
    publicKey = builtins.readFile ./id_rsa.pub;
  };

  machine = { pkgs, resources, ... }:
  {
    imports = [ ../../bootstrap/fetchHetznerKeys.nix ];

    config = {
      deployment.targetEnv = "hetznercloud";
      deployment.hetznercloud = {
        serverType = "cx11";
        location = "hel1";
        sshKeys = [ resources.hetznercloudSshKeys.test-key ];
      };

      services.fetchHetznerKeys.enable = true;
    };
  };
}
