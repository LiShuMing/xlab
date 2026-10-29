import Lake
open Lake DSL

package xlabLean where
  moreLeanArgs := #["-DwarningAsError=true"]

lean_lib Xlab

@[default_target]
lean_exe «xlab-lean» where
  root := `Main

lean_exe «xlab-tests» where
  root := `Tests
