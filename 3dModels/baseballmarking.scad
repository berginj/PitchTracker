/*  Baseball / 12" Softball Marking Jig (Two-Part Clamshell) — OpenSCAD
    Goal: consistent, high-contrast, camera-trackable markings.

    What’s new vs basic window-only jig:
    - Keep REQUIRED 0.5" access windows
    - Add a small "stencil aperture" near the ball surface to make crisp, consistent dot marks
    - Use Fibonacci (quasi-uniform) distribution to avoid symmetric ring ambiguity
    - Optional index feature: one window produces a DOUBLE-DOT to anchor orientation

    Export:
      show="top"    -> render top half, export STL
      show="bottom" -> render bottom half, export STL
*/

$fn = 160;

// ---------- WHAT TO SHOW ----------
show = "both";            // "top", "bottom", "both", "assembled"

// ---------- BALL PRESET ----------
ball_type = "softball12";   // "baseball", "softball12", "custom"

// Baseball: diameter-based (measure yours for best fit)
baseball_d_in = 2.90;

// 12" softball is circumference-based (12.00 inches circumference by name)
softball12_circ_in = 12.00;

// Custom: set either diameter or circumference (in); leave the other 0
custom_d_in    = 0;
custom_circ_in = 0;

function ball_diameter_in() =
    (ball_type == "baseball")   ? baseball_d_in :
    (ball_type == "softball12") ? (softball12_circ_in / PI) :
    (custom_d_in > 0)           ? custom_d_in :
    (custom_circ_in > 0)        ? (custom_circ_in / PI) :
                                  baseball_d_in;

// ---------- FIT ----------
mm_per_in = 25.4;
clearance_mm = 0.50;      // + looser, - tighter. Start ~0.4–0.8mm depending on printer.

// ---------- SHELL ----------
wall_mm = 6.5;

// ---------- WINDOW + STENCIL (CLARITY CONTROL) ----------
// REQUIRED access opening size:
access_d_in = 0.50;
access_oversize_mm = 0.40;       // tolerance for printing / marker entry

// Stencil aperture near the ball surface (this controls dot size!)
stencil_d_in = 0.30;             // ~0.30" dot is very camera-friendly
stencil_oversize_mm = 0.20;      // tolerance; increase if marker drags

stencil_len_mm = 2.2;            // thickness of the "stencil throat" inside the shell
start_inside_cavity_mm = 1.0;    // begins cut slightly inside cavity for robust booleans

// Avoid cutting holes too close to the seam (keeps clamp strength)
seam_exclusion_deg = 10;         // exclude holes within ±this latitude around equator

// ---------- HOLE DISTRIBUTION (DEFAULT: camera-friendly) ----------
pattern = "fibonacci";           // "fibonacci" recommended for tracking
holes_total = 40;                // total windows over full sphere (half appear per half)

// ---------- INDEX FEATURE (HIGHLY RECOMMENDED) ----------
use_index = true;                // one special location becomes a double-dot stencil
index_i = 0;                     // which Fibonacci point becomes index (i=0 lands near north pole)
index_sep_mm = 6.0;              // separation between the two index dots (mm)

// ---------- ALIGNMENT ----------
pin_count = 3;
pin_d_mm = 5.0;
pin_len_mm = 10.0;
pin_clear_mm = 0.25;
pin_phase_deg = 20;

// ---------- SEAM (optional tongue/groove) ----------
use_tongue_groove = true;
tg_height_mm = 2.5;
tg_width_mm  = 3.0;
tg_clear_mm  = 0.25;
seam_margin_mm = 1.5;

// ---------- DERIVED ----------
eps = 0.01;

ball_d_in = ball_diameter_in();
ball_d_mm = ball_d_in * mm_per_in;

inner_r = ball_d_mm/2 + clearance_mm;
outer_r = inner_r + wall_mm;

access_d_mm  = access_d_in  * mm_per_in + access_oversize_mm;
stencil_d_mm = stencil_d_in * mm_per_in + stencil_oversize_mm;

// Radii for tongue/groove near outer edge
tg_r_outer = outer_r - seam_margin_mm;
tg_r_inner = tg_r_outer - tg_width_mm;

// Pins inside tongue/groove
pin_r = tg_r_inner - (pin_d_mm/2) - 2.0;

// Along radial axis in the rotated coordinate frame:
t_inner_start = inner_r - start_inside_cavity_mm;
t_stencil_end = inner_r + stencil_len_mm;  // where stencil throat ends
t_access_start = t_stencil_end;            // access bore begins right after stencil throat

// ---------- HELPERS ----------
module halfspace(is_top, r){
  translate([0,0, is_top ? (r/2) : (-r/2)])
    cube([2*r + 20, 2*r + 20, r + 2*eps], center=true);
}

module hemi_solid(is_top){
  intersection(){
    sphere(r=outer_r);
    halfspace(is_top, outer_r);
  }
}

module hemi_cavity(is_top){
  intersection(){
    sphere(r=inner_r);
    halfspace(is_top, inner_r);
  }
}

// Build one marking window oriented at (theta, phi).
// - Outer: 0.5" access bore to the outside
// - Inner: smaller stencil throat near the ball to force a crisp dot size
module marking_window(theta_deg, phi_deg, is_index=false){
  rotate([0, theta_deg, phi_deg]) {
    // Inner stencil: cut only a SMALL aperture near the ball surface
    // This makes the final dot sharp and consistent.
    if(!is_index){
      translate([0,0, t_inner_start])
        cylinder(d=stencil_d_mm,
                 h=(t_stencil_end - t_inner_start + 0.6), center=false);
    } else {
      // Index = double-dot stencil (camera can always identify orientation)
      translate([0,0, t_inner_start]) {
        translate([+index_sep_mm/2, 0, 0])
          cylinder(d=stencil_d_mm, h=(t_stencil_end - t_inner_start + 0.6), center=false);
        translate([-index_sep_mm/2, 0, 0])
          cylinder(d=stencil_d_mm, h=(t_stencil_end - t_inner_start + 0.6), center=false);
      }
    }

    // Outer access bore: REQUIRED 0.5" window from just outside stencil to the exterior
    translate([0,0, t_access_start])
      cylinder(d=access_d_mm,
               h=(outer_r - t_access_start + 3), center=false);
  }
}

module windows_for_half(is_top){
  if(pattern == "fibonacci"){
    golden = 180 * (3 - sqrt(5)); // degrees

    for(i = [0:holes_total-1]){
      z = 1 - 2*(i + 0.5)/holes_total; // -1..1
      lat = asin(z);                   // degrees, -90..90
      theta = acos(z);                 // degrees, 0..180
      phi = i * golden;                // degrees

      // Exclude near seam to keep strength + avoid cutting tongue/groove
      if(abs(lat) >= seam_exclusion_deg){

        // top half gets z>=0, bottom gets z<0
        if( (is_top && z >= 0) || (!is_top && z < 0) ){
          marking_window(theta, phi, use_index && (i == index_i) && is_top);
        }
      }
    }
  }
  else {
    // If you ever want rings back, you can re-add the ring code here.
  }
}

module pins_male(){
  for(i=[0:pin_count-1]){
    a = i*360/pin_count + pin_phase_deg;
    translate([pin_r*cos(a), pin_r*sin(a), pin_len_mm/2])
      cylinder(d=pin_d_mm, h=pin_len_mm, center=true);
  }
}

module pins_female(){
  for(i=[0:pin_count-1]){
    a = i*360/pin_count + pin_phase_deg;
    translate([pin_r*cos(a), pin_r*sin(a), -pin_len_mm/2])
      cylinder(d=pin_d_mm + 2*pin_clear_mm, h=pin_len_mm + 2, center=true);
  }
}

module tongue(){
  if(use_tongue_groove){
    difference(){
      translate([0,0, tg_height_mm/2]) cylinder(r=tg_r_outer, h=tg_height_mm, center=true);
      translate([0,0, tg_height_mm/2]) cylinder(r=tg_r_inner, h=tg_height_mm+2, center=true);
    }
  }
}

module groove(){
  if(use_tongue_groove){
    difference(){
      translate([0,0, -tg_height_mm/2])
        cylinder(r=tg_r_outer + tg_clear_mm, h=tg_height_mm, center=true);
      translate([0,0, -tg_height_mm/2])
        cylinder(r=tg_r_inner - tg_clear_mm, h=tg_height_mm+2, center=true);
    }
  }
}

// ---------- PARTS ----------
module jig_half(is_top){
  difference(){
    union(){
      hemi_solid(is_top);

      // Bottom half: male pins + tongue (protrude into top half)
      if(!is_top){
        pins_male();
        tongue();
      }
    }

    // cavity
    hemi_cavity(is_top);

    // windows (with stencil throats)
    windows_for_half(is_top);

    // Top half: sockets + groove
    if(is_top){
      pins_female();
      groove();
    }
  }
}

// ---------- DISPLAY ----------
if(show == "top"){
  jig_half(true);
}
else if(show == "bottom"){
  jig_half(false);
}
else if(show == "assembled"){
  jig_half(false);
  jig_half(true);
}
else { // "both"
  translate([-(outer_r+18),0,0]) jig_half(false);
  translate([(outer_r+18),0,0])  jig_half(true);
}
