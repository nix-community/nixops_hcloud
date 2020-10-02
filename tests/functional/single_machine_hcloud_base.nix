{
  network = {};

  resources.hcloudSshKeys.test-key = {
    publicKey = builtins.readFile ./id_rsa.pub;
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
