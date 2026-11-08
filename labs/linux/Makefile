.PHONY: kernel-lens run_kernel_lens test_kernel_lens

kernel-lens:
	cargo build --locked --manifest-path kernel-lens/Cargo.toml

run_kernel_lens:
	cargo run --release --locked --manifest-path kernel-lens/Cargo.toml

test_kernel_lens:
	cargo test --locked --manifest-path kernel-lens/Cargo.toml
