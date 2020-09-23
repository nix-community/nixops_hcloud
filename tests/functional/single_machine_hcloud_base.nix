{
  network = {};
  machine = { pkgs, ... }:
  {
    deployment.targetEnv = "hetznercloud";
    deployment.hetznercloud = {
      serverType = "cx11";
      image = 22969353;
      location = "hel1";
    };
  };
}
