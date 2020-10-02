{
  config_exporters = { optionalAttrs, ... }: [
    (config: { hcloud = optionalAttrs (config.deployment.targetEnv == "hcloud") config.deployment.hcloud; })
  ];
  options = [
    ./hcloud.nix
  ];
  resources = { evalResources, zipAttrs, resourcesByType, ... }: {
    hcloudSshKeys = evalResources ./hcloud_sshkey.nix (zipAttrs resourcesByType.hcloudSshKeys or []);
    hcloudVolumes = evalResources ./hcloud_volume.nix (zipAttrs resourcesByType.hcloudVolumes or []);
  };
}
