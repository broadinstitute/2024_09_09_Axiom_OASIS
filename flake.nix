{
  description = "2024_09_09_Axiom_OASIS - reproduction environment (paper 1A)";

  # The R derivation below is adapted from broadinstitute/2025_04_13_OASIS_CellPainting
  # (paper 1B), which solved the same fastbmdR packaging problem first. Kept here so
  # this public repo is self-contained.

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config = {
            allowUnfree = true;
            nvidia.acceptLicense = true;
          };
        };

        # fastbmdR ships a DESCRIPTION with no Imports/Depends fields, so
        # remotes::install_github() installs it with none of its dependencies.
        # Its NAMESPACE still does `import(data.table)` and
        # `importFrom(drc, neill.test)`, so library(fastbmdR) hard-fails without
        # them. Supply both explicitly.
        fastbmdR = pkgs.rPackages.buildRPackage {
          name = "fastbmdR";
          src = pkgs.fetchFromGitHub {
            owner = "jessica-ewald";
            repo = "fastbmdR";
            rev = "v0.0.0.9000";
            sha256 = "sha256-YQ2Lr7NR2eEBKNRNOEy7C97Ekl2+pnZZT/73KY1Xh8Q=";
          };
          propagatedBuildInputs = with pkgs.rPackages; [ drc data_table ];
        };

        # Package set derived by reading 1_snakemake/concresponse/*.R:
        #   compute_distances.R  dplyr arrow foreach doParallel stringr (+parallel, stats)
        #   gmd_functions.R      dplyr arrow
        #   cmd_functions.R      dplyr arrow
        #   fit_curves.R         dplyr arrow fastbmdR
        #   fit_curves_meta.R    dplyr arrow fastbmdR
        #   select_pod.R         dplyr arrow data.table
        #   plot_meta_curve.R    dplyr arrow ggplot2 ggforce reshape2 fastbmdR
        #   plot_cp_curve.R      dplyr arrow ggplot2 ggforce fastbmdR
        #                        (+ reshape2::melt at line 122, never require()d)
        rEnv = pkgs.rWrapper.override {
          packages = with pkgs.rPackages; [
            dplyr
            arrow
            ggplot2
            ggforce
            reshape2
            foreach
            doParallel
            data_table
            stringr
            drc
          ] ++ [ fastbmdR ];
        };
      in
      {
        # Default shell: R from Nix, Python and snakemake from pixi.
        # On NixOS, conda-provided R has problems with system() calls, so R comes
        # from Nix rather than from a pixi environment.
        #
        # snakemake deliberately does NOT come from Nix: requirements.txt pins
        # snakemake==7.32.4, nixpkgs ships 9.x, and the nixpkgs build currently
        # fails to evaluate anyway (its python3.14-stopit dependency is marked
        # broken). Taking it from pixi honours the pin.
        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            pixi
            rEnv
            awscli2
          ];

          shellHook = ''
            echo "2024_09_09_Axiom_OASIS - reproduction environment"
            echo ""
            echo "  R + awscli : from Nix (this shell)"
            echo "  Python     : pixi run -e pipeline / -e notebooks"
            echo ""
            echo "Pipeline runs from 1_snakemake/ (R scripts source ./concresponse/*.R):"
            echo "  cd 1_snakemake"
            echo "  pixi run -e pipeline snakemake --configfile inputs/conf/cpcnn.json --cores 32 -n"
            echo ""
            # fastbmdR is baked into the Nix R env; stop the .R scripts from
            # attempting install.packages()/install_github() inside snakemake jobs.
            export R_LIBS_USER=/dev/null
          '';

          # cupy and the GPU xgboost build need the host driver's libcuda.so,
          # which on NixOS lives here rather than on the default loader path.
          LD_LIBRARY_PATH = "/run/opengl-driver/lib";
        };
      });
}
