self: super:
let
  lib = self.lib;
in
{
  cloud-init =
    let
      version = "20.3";
      pythonPackages = self.python38Packages;
    in pythonPackages.buildPythonApplication {
      pname = "cloud-init";
      inherit version;
      namePrefix = "";

      src = builtins.fetchurl {
        url = "https://launchpad.net/cloud-init/trunk/${version}/+download/cloud-init-${version}.tar.gz";
        sha256 = "0wcsv3p1f2y1g8pv7yl4ddq9jz48ll8583zrpmzlfxfmw3g7aqw4";
      };

      patches = [ ./cloud-init-nixos.patch ];
      prePatch = ''
          patchShebangs ./tools
          substituteInPlace setup.py \
            --replace '= "/"' '= "'$out'/"' \
            --replace 'self.init_system = ""' 'self.init_system = "systemd"'
          substituteInPlace cloudinit/config/cc_growpart.py \
            --replace 'subp.subp(["growpart"' 'subp.subp(["${self.cloud-utils}/bin/growpart"'
          # Argparse is part of python stdlib
          sed -i s/argparse// requirements.txt
          '';

      propagatedBuildInputs = with pythonPackages;
        [ jinja2 oauthlib configobj pyyaml requests jsonpatch jsonschema ];

      checkInputs = with pythonPackages; [ contextlib2 httpretty mock unittest2 ];

      doCheck = false;

      meta = {
        homepage = https://cloudinit.readthedocs.org;
        description = "Provides configuration and customization of cloud instance";
        maintainers = [ lib.maintainers.madjar lib.maintainers.phile314 ];
        platforms = lib.platforms.all;
      };
    };
}
