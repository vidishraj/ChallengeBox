// Problem 2: Framed delivery records for segmented text.
//
// GROUND-TRUTH SOLUTION: literal per-character simulation of the chunking rules.
// Correct by construction. Complexity is O(N + S + sum over requests of (R-L+1)).
//
// COMPLEXITY CAVEAT (see trap log): with N,Q <= 5e5, the summed request spans can
// reach ~2.5e11 character-steps, which this literal version cannot do inside a
// tight runtime limit. The bounds force a sublinear-per-query method (per-position
// "next chunk boundary" precompute + binary lifting over chunks with prefix sums,
// and a within-chunk binary search for the budget cutoff) giving O((N+Q) log N).
// That design is documented in the trap log; this file is the correctness oracle
// and is exact on any input small enough to run.
//
// std only; reads stdin, writes stdout; deterministic.

use std::io::{self, Read, Write};

fn width(cp: u32) -> u64 {
    if cp <= 0x7F {
        1
    } else if cp <= 0x7FF {
        2
    } else if cp <= 0xFFFF {
        3
    } else {
        4
    }
}

fn main() {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input).unwrap();
    let bytes = input.as_bytes();
    let mut pos = 0usize;

    // lightweight whitespace-delimited token reader
    let next_u64 = |pos: &mut usize| -> u64 {
        while *pos < bytes.len() && (bytes[*pos] as char).is_ascii_whitespace() {
            *pos += 1;
        }
        let mut v: u64 = 0;
        while *pos < bytes.len() && bytes[*pos].is_ascii_digit() {
            v = v * 10 + (bytes[*pos] - b'0') as u64;
            *pos += 1;
        }
        v
    };
    let next_hex = |pos: &mut usize| -> u32 {
        while *pos < bytes.len() && (bytes[*pos] as char).is_ascii_whitespace() {
            *pos += 1;
        }
        let mut v: u32 = 0;
        while *pos < bytes.len() && bytes[*pos].is_ascii_hexdigit() {
            let c = bytes[*pos];
            let d = if c.is_ascii_digit() {
                (c - b'0') as u32
            } else {
                (c.to_ascii_lowercase() - b'a') as u32 + 10
            };
            v = v * 16 + d;
            *pos += 1;
        }
        v
    };

    let n = next_u64(&mut pos) as usize;
    let s = next_u64(&mut pos) as usize;
    let q = next_u64(&mut pos) as usize;
    let c = next_u64(&mut pos); // chunk payload cap (>=4)
    let h = next_u64(&mut pos); // header wire bytes

    // widths, 1-based (index 0 unused)
    let mut w = vec![0u64; n + 1];
    for i in 1..=n {
        w[i] = width(next_hex(&mut pos));
    }

    // seg_of[i] = segment index (0-based) for 1-based position i
    let mut seg_of = vec![0u32; n + 1];
    {
        let mut idx = 1usize;
        for seg in 0..s {
            let len = next_u64(&mut pos) as usize;
            for _ in 0..len {
                seg_of[idx] = seg as u32;
                idx += 1;
            }
        }
    }

    let mut out = String::with_capacity(q * 24);
    for _ in 0..q {
        let l = next_u64(&mut pos) as usize;
        let r = next_u64(&mut pos) as usize;
        let b = next_u64(&mut pos);

        let mut payload: u64 = 0;
        let mut wire: u64 = 0;
        let mut chars: u64 = 0;
        let mut last: usize = 0;
        let mut chunks: u64 = 0;
        let mut last_chunk_payload: u64 = 0;

        let mut open = false;
        let mut cur_seg: u32 = 0;
        let mut cur_chunk_payload: u64 = 0;
        let mut cause = "END";

        let mut i = l;
        while i <= r {
            let wi = w[i];
            let need_new = !open || seg_of[i] != cur_seg || cur_chunk_payload + wi > c;
            let incr = wi + if need_new { h } else { 0 };
            // wire <= b <= 1e18, incr <= h+4 <= ~1e18; use u128 to be overflow-proof
            if (wire as u128) + (incr as u128) > (b as u128) {
                cause = "LIMIT";
                break;
            }
            wire += incr;
            payload += wi;
            chars += 1;
            last = i;
            if need_new {
                chunks += 1;
                cur_chunk_payload = wi;
                cur_seg = seg_of[i];
                open = true;
            } else {
                cur_chunk_payload += wi;
            }
            last_chunk_payload = cur_chunk_payload;
            i += 1;
        }

        out.push_str(&format!(
            "{} {} {} {} {} {} {}\n",
            payload, wire, chars, last, chunks, last_chunk_payload, cause
        ));
    }

    io::stdout().write_all(out.as_bytes()).unwrap();
}
