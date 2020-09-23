{ sources ? import ./sources.nix }:
let
  overlay = _: pkgs: {
    niv = (pkgs.callPackage sources.niv {}).niv;
  };
in
  import sources.nixpkgs { overlays = [overlay]; config = {}; }
