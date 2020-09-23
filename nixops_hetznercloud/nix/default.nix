{
  config_exporters = { optionalAttrs, ... }: [
    (config: { hetznercloud = optionalAttrs (config.deployment.targetEnv == "hetznercloud") config.deployment.hetznercloud; })
  ];
  options = [
    ./hetznercloud.nix
  ];
  resources = { evalResources, zipAttrs, resourcesByType, ... }: { };
}
