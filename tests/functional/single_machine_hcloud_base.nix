{
  network = {};
  machine = { pkgs, ... }:
  {
    deployment.targetEnv = "hetznercloud";
    deployment.hetznercloud = {
      serverType = "cx11";
      location = "hel1";
    };
  };
}
