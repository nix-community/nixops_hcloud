{
  network = {};
  machine = { pkgs, ... }:
  {
    imports = [ ../../bootstrap/fetchHetznerKeys.nix ];

    config = {
      deployment.targetEnv = "hetznercloud";
      deployment.hetznercloud = {
        serverType = "cx11";
        location = "hel1";
      };

      services.fetchHetznerKeys.enable = true;
    };
  };
}
