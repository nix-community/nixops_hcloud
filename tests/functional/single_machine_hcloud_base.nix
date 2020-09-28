{
  network = {};
  machine = { pkgs, ... }:
  {
    deployment.targetEnv = "hetznercloud";
    deployment.hetznercloud = {
      serverType = "cx11";
      location = "hel1";
    };

    services.cloud-init.enable = true;
  };
}
