{ pkgs ? import ./nix/nixpkgs.nix {} }:
let
  overrides = import ./overrides.nix { inherit pkgs; };
in pkgs.mkShell {
  buildInputs = [
    pkgs.niv
    (pkgs.poetry2nix.mkPoetryEnv {
      projectDir = ./.;
      overrides = pkgs.poetry2nix.overrides.withDefaults overrides;
    })
    pkgs.poetry
  ];
}

