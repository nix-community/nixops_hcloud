{
  network = {};

  resources.hcloudSshKeys.test-key = {
    publicKey = builtins.readFile ./id_rsa.pub;
  };

  resources.hcloudVolumes.test-vol = {
    size = 10;
    location = "hel1";
  };

  machine = { pkgs, resources, ... }:
  {
    imports = [ ../../bootstrap/fetchHetznerKeys.nix ];

    config = {
      deployment.targetEnv = "hcloud";
      deployment.hcloud = {
        serverType = "cx11";
        location = "hel1";
        sshKeys = [ resources.hcloudSshKeys.test-key ];
      };

      services.fetchHetznerKeys.enable = true;
    };
  };
}
