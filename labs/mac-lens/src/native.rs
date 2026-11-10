//! Small native boundaries. All calls are read-only; no sudo.
//! macmon may fall back to read-only system_profiler during initialization.
#[cfg(all(target_os = "macos", target_arch = "aarch64"))]
use crate::model::finite;
use crate::model::Gpu;
use std::time::Duration;

#[derive(Default)]
pub struct Vm {
    pub pressure: Option<String>,
    pub compressed: Option<u64>,
    pub swap_in_bytes: Option<u64>,
    pub swap_out_bytes: Option<u64>,
    pub reason: String,
}

#[cfg(target_os = "macos")]
#[allow(deprecated)] // libc's Mach bindings are deprecated, not the underlying read-only OS APIs.
pub fn vm() -> Vm {
    let mut result = Vm::default();
    // SAFETY: fixed-size output buffers, lengths checked before interpretation;
    // host_statistics64 owns no output allocations. Release our host send right.
    unsafe {
        let mut level: i32 = 0;
        let mut length = std::mem::size_of::<i32>();
        if libc::sysctlbyname(
            c"kern.memorystatus_vm_pressure_level".as_ptr(),
            (&mut level as *mut i32).cast(),
            &mut length,
            std::ptr::null_mut(),
            0,
        ) == 0
            && length == std::mem::size_of::<i32>()
        {
            result.pressure = match level {
                1 => Some("normal"),
                2 => Some("warning"),
                4 => Some("critical"),
                _ => None,
            }
            .map(str::to_owned);
        }
        let host = libc::mach_host_self();
        let mut stats = std::mem::zeroed::<libc::vm_statistics64>();
        let mut count = libc::HOST_VM_INFO64_COUNT;
        let status = libc::host_statistics64(
            host,
            libc::HOST_VM_INFO64,
            (&mut stats as *mut libc::vm_statistics64).cast(),
            &mut count,
        );
        let page_size = libc::sysconf(libc::_SC_PAGESIZE);
        mach2::mach_port::mach_port_deallocate(libc::mach_task_self(), host);
        // New SDKs append fields; older macOS returns a shorter revision. Only
        // require the prefix through compressor_page_count, which we read.
        let needed = (std::mem::offset_of!(libc::vm_statistics64, compressor_page_count)
            + std::mem::size_of::<u32>())
            / std::mem::size_of::<libc::integer_t>();
        if status == libc::KERN_SUCCESS && count as usize >= needed && page_size > 0 {
            let page = page_size as u64;
            result.compressed = u64::from(stats.compressor_page_count).checked_mul(page);
            result.swap_in_bytes = stats.swapins.checked_mul(page);
            result.swap_out_bytes = stats.swapouts.checked_mul(page);
        } else {
            result.reason = "Mach VM counters unavailable".into();
        }
    }
    if result.pressure.is_none() {
        result
            .reason
            .push_str("; memory pressure sysctl unavailable/unknown");
    }
    result
}

#[cfg(not(target_os = "macos"))]
pub fn vm() -> Vm {
    Vm {
        reason: "Native memory pressure requires macOS".into(),
        ..Default::default()
    }
}

pub struct GpuSampler {
    #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
    sampler: Option<macmon::Sampler>,
    reason: String,
}

impl GpuSampler {
    // Construct on the collection thread: macmon's native handles are not sent
    // between threads. The UI never blocks on IOReport's sample interval.
    pub fn new(enabled: bool) -> Self {
        #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
        {
            if enabled {
                match macmon::Sampler::new() {
                    Ok(sampler) if !sampler.get_soc_info().vm && sampler.get_soc_info().gpu_freqs.len() > 1 =>
                        return Self { sampler: Some(sampler), reason: String::new() },
                    Ok(_) => return Self { sampler: None, reason: "GPU unavailable in VM or frequency table missing".into() },
                    Err(_) => return Self { sampler: None, reason: "macmon initialization failed; GPU/SMC/IOReport unavailable (try --no-gpu)".into() },
                }
            }
            Self {
                sampler: None,
                reason: "GPU sampling disabled (--no-gpu)".into(),
            }
        }
        #[cfg(not(all(target_os = "macos", target_arch = "aarch64")))]
        {
            let _ = enabled;
            Self {
                reason: "Apple GPU collection requires Apple Silicon macOS".into(),
            }
        }
    }

    pub fn sample(&mut self, interval: Duration) -> Gpu {
        #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
        if let Some(sampler) = &mut self.sampler {
            match sampler.get_metrics(interval.as_millis() as u32) {
                Ok(metrics) => {
                    // macmon defaults some unsupported counters to zero. A valid
                    // residency window needs a usable frequency; do not relabel
                    // missing data as an idle GPU. Zero power is conservative N/A.
                    let valid = metrics.gpu_freq_mhz > 0;
                    return Gpu {
                        active_percent: valid.then(|| finite(f64::from(metrics.gpu_active_ratio) * 100.0, 0.0, 100.0)).flatten(),
                        frequency_mhz: valid.then_some(metrics.gpu_freq_mhz),
                        power_watts: finite(f64::from(metrics.gpu_power), f64::MIN_POSITIVE, 2000.0),
                        cpu_power_watts: finite(f64::from(metrics.cpu_power), f64::MIN_POSITIVE, 2000.0),
                        temperature_c: metrics.temp.gpu_temp_avg.and_then(|t| finite(f64::from(t), 0.1, 150.0)),
                        reason: if valid { "macmon/IOReport: GPU active residency, NOT compute occupancy; power estimate; zero/absent power => N/A" } else { "No valid GPU residency/frequency window; not interpreted as 0%" }.into(),
                    };
                }
                Err(_) => {
                    self.reason =
                        "macmon sampling failed; GPU metrics unavailable until restart".into();
                    self.sampler = None;
                    return Gpu {
                        reason: self.reason.clone(),
                        ..Default::default()
                    };
                }
            }
        }
        std::thread::sleep(interval);
        Gpu {
            reason: self.reason.clone(),
            ..Default::default()
        }
    }
}
