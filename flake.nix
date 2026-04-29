{
  description = "Python library and CLI for managing Linux gaming compatibility tools";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
    };
  };

  outputs = {
    self,
    flake-utils,
    nixpkgs,
    pyproject-nix,
    pyproject-build-systems,
    uv2nix,
  }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;
        };

        lib = pkgs.lib;

        python = pkgs.python311;

        workspace = uv2nix.lib.workspace.loadWorkspace {
          workspaceRoot = ./.;
        };

        overlay = workspace.mkPyprojectOverlay {
          sourcePreference = "wheel";
        };

        editableOverlay = workspace.mkEditablePyprojectOverlay {
          root = "$REPO_ROOT";
        };

        baseSet = pkgs.callPackage pyproject-nix.build.packages {
          inherit python;
        };

        pythonSet = baseSet.overrideScope (
          lib.composeManyExtensions [
            pyproject-build-systems.overlays.wheel
            overlay
            (final: prev: {
              steam = prev.steam.overrideAttrs (old: {
                nativeBuildInputs = old.nativeBuildInputs ++ final.resolveBuildSystem {
                  setuptools = [ ];
                };
              });

              vdf = prev.vdf.overrideAttrs (old: {
                nativeBuildInputs = old.nativeBuildInputs ++ final.resolveBuildSystem {
                  setuptools = [ ];
                };
              });
            })
          ]
        );

        editablePythonSet = pythonSet.overrideScope editableOverlay;

        mkApplication = (pkgs.callPackage pyproject-nix.build.util { }).mkApplication;

        protondlPackage = pythonSet.protondl;

        protondlVenv = pythonSet.mkVirtualEnv "protondl-env" (
          workspace.deps.default
          // {
            protondl = [ "cli" ];
          }
        );

        protondlApp = mkApplication {
          package = protondlPackage;
          venv = protondlVenv;
        };

        devVenv = editablePythonSet.mkVirtualEnv "protondl-dev-env" (
          workspace.deps.all
          // {
            protondl = [ "cli" ];
          }
        );
      in
      {
        packages = {
          default = protondlApp;
          protondl = protondlPackage;
          protondl-app = protondlApp;
        };

        apps = {
          default = flake-utils.lib.mkApp { drv = protondlApp; };
          protondl = flake-utils.lib.mkApp { drv = protondlApp; };
        };

        devShells.default = pkgs.mkShell {
          packages = [
            devVenv
            pkgs.uv
          ];

          env = {
            UV_NO_SYNC = "1";
            UV_PYTHON = editablePythonSet.python.interpreter;
            UV_PYTHON_DOWNLOADS = "never";
          };

          shellHook = ''
            unset PYTHONPATH
            export REPO_ROOT=$(git rev-parse --show-toplevel)
          '';
        };

        formatter = pkgs.nixfmt-rfc-style;
      }
    );
}