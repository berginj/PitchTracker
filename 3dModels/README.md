# OpenSCAD Mount

```scad
// Dual Arducam 3-foot baseline — dovetail key joints — Bambu P1P friendly
// Units: mm
// Export: set PART below, F6, File -> Export -> STL

$fn = 64;

// -------------------- Parameters --------------------
inch = 25.4;

// Desired camera-to-camera distance (screw center to screw center)
BASELINE   = 36*inch;     // 914.4 mm

// How far OUTBOARD of each bar end plane the camera screw center sits
// (needed so the hole isn't split on the very edge)
CAM_OFFSET = 12;          // mm (tune if you want cameras closer to the bar ends)

// Bar end-to-end length between the two segment end planes
BAR_LEN = BASELINE - 2*CAM_OFFSET;

// Segmenting for P1P bed
N_SEG   = 4;
SEG_LEN = BAR_LEN / N_SEG;

// Beam section (solid)
BEAM_W = 35;  // Y
BEAM_H = 25;  // Z

// Dovetail pocket/key
SLOT_LEN = 40;            // pocket depth into each end
KEY_LEN  = 2*SLOT_LEN;    // bridges two pockets

DT_H    = 20;             // dovetail height (in Z)
DT_TOP  = 14;             // narrow width (in Y)
DT_BOT  = 20;             // wide width (in Y)
FIT     = 0.28;           // clearance for PETG (try 0.20 for PLA)

// Lock bolt (through the segment side into key's captive nut)
LOCK_OFF   = 20;          // mm from each end face
M4_CLR     = 4.6;
M4_HEAD_D  = 8.6;
M4_HEAD_H  = 3.4;

M4_NUT_AF  = 7.2;
M4_NUT_T   = 3.4;

// Place lock low inside dovetail so nut pocket can open downward and be trapped by beam wall
function hex_r(af) = af / (2*cos(30));
LOCK_Z = -DT_H/2 + hex_r(M4_NUT_AF) - 0.2;

// Camera mount plate (fully supported by body below — no cantilever)
CAM_PLATE = 60;           // plate width in Y
CAM_T     = 8;            // plate thickness in Z
QTR_CLR   = 7.0;          // 1/4"-20 clearance hole

CAM_BODY   = 55;          // mount length outward from bar end plane (must be > SLOT_LEN and > LOCK_OFF)
CAM_KNOB_D = 18;          // underside access well diameter for thumb/D-ring screw

// Tripod clamp
CLAMP_LEN = 70;
CLAMP_PAD = 7;            // wall thickness around beam pocket
CLAMP_CLR = 0.35;         // clearance around beam in clamp pocket

QTR_NUT_AF = 11.35;       // 1/4"-20 hex nut across flats (7/16" ≈ 11.11) + clearance
QTR_NUT_T  = 5.8;

// -------------------- Choose what to render --------------------
// "segment", "key", "camera_mount_left", "camera_mount_right", "tripod_top", "tripod_bottom"
PART = "tripod_bottom";

// -------------------- Helpers --------------------
module hex_prism(af, h){
  cylinder(r=hex_r(af), h=h, $fn=6);
}

// Dovetail prism: polygon in (Y,Z), extrude along +X after rotation
module dovetail_prism(len, top_w, bot_w, h){
  rotate([0,90,0])
    linear_extrude(height=len)
      polygon(points=[
        [-top_w/2,  h/2],
        [ top_w/2,  h/2],
        [ bot_w/2, -h/2],
        [-bot_w/2, -h/2]
      ]);
}

module beam_body(len){
  // centered in Y,Z for easier placement
  translate([0, -BEAM_W/2, -BEAM_H/2])
    cube([len, BEAM_W, BEAM_H], center=false);
}

// -------------------- Parts --------------------
module segment(){
  difference(){
    beam_body(SEG_LEN);

    // Dovetail pockets at each end (slightly oversized for fit)
    // Near end pocket: opens at x=0 and goes inward (+X)
    dovetail_prism(SLOT_LEN, DT_TOP+2*FIT, DT_BOT+2*FIT, DT_H+2*FIT);

    // Far end pocket: opens at x=SEG_LEN and goes inward (-X)
    translate([SEG_LEN - SLOT_LEN, 0, 0])
      dovetail_prism(SLOT_LEN, DT_TOP+2*FIT, DT_BOT+2*FIT, DT_H+2*FIT);

    // Lock bolt holes: one per end, through Y (beam width)
    for (xpos = [LOCK_OFF, SEG_LEN - LOCK_OFF]){
      // clearance through
      translate([xpos, 0, LOCK_Z])
        rotate([90,0,0]) cylinder(d=M4_CLR, h=BEAM_W+1, center=true);

      // counterbore for bolt head on -Y side
      translate([xpos, -BEAM_W/2 + (M4_HEAD_H/2), LOCK_Z])
        rotate([90,0,0]) cylinder(d=M4_HEAD_D, h=M4_HEAD_H+0.2, center=true);
    }
  }
}

module key(){
  difference(){
    // The dovetail key (slightly smaller than pocket)
    dovetail_prism(KEY_LEN, DT_TOP, DT_BOT, DT_H);

    // Two lock bolt holes + nut traps (one for each segment end)
    for (xpos = [LOCK_OFF, KEY_LEN - LOCK_OFF]){
      // bolt clearance through key
      translate([xpos, 0, LOCK_Z])
        rotate([90,0,0]) cylinder(d=M4_CLR, h=DT_H+6, center=true);

      // nut trap (axis along Y), placed low so it opens downward,
      // then becomes trapped when key is inserted into a beam pocket.
      translate([xpos, 0, LOCK_Z])
        rotate([90,0,0]) hex_prism(M4_NUT_AF, M4_NUT_T+0.6);
    }
  }
}

// Camera mount (LEFT end):
// - Mating face is the bar end plane at x=0
// - Key slides into the mount from that face (opening is visible on x=0 face)
// - Camera screw center is at x = -CAM_OFFSET (outboard), so the hole is fully supported
module camera_mount_left(){
  difference(){
    union(){
      // Solid body exists only outboard of bar end plane: x in [-CAM_BODY, 0]
      translate([-CAM_BODY, -BEAM_W/2, -BEAM_H/2])
        cube([CAM_BODY, BEAM_W, BEAM_H], center=false);

      // Top plate (fully supported; same X footprint as body)
      translate([-CAM_BODY, -CAM_PLATE/2, BEAM_H/2])
        cube([CAM_BODY, CAM_PLATE, CAM_T], center=false);
    }

    // Dovetail pocket opens on mating face at x=0 and goes INTO mount (negative X)
    translate([-SLOT_LEN, 0, 0])
      dovetail_prism(SLOT_LEN, DT_TOP+2*FIT, DT_BOT+2*FIT, DT_H+2*FIT);

    // Lock bolt hole (into mount from mating face)
    translate([-LOCK_OFF, 0, LOCK_Z])
      rotate([90,0,0]) cylinder(d=M4_CLR, h=BEAM_W+1, center=true);

    // Counterbore for bolt head on -Y side
    translate([-LOCK_OFF, -BEAM_W/2 + (M4_HEAD_H/2), LOCK_Z])
      rotate([90,0,0]) cylinder(d=M4_HEAD_D, h=M4_HEAD_H+0.2, center=true);

    // 1/4"-20 clearance hole through plate (camera screw passes up into camera)
    translate([-CAM_OFFSET, 0, BEAM_H/2 - 0.1])
      cylinder(d=QTR_CLR, h=CAM_T + 0.3, center=false);

    // Underside access well for thumb/D-ring screw head
    translate([-CAM_OFFSET, 0, -BEAM_H/2 - 0.1])
      cylinder(d=CAM_KNOB_D, h=BEAM_H + 0.35, center=false);
  }
}

// Camera mount (RIGHT end): mirror of left
module camera_mount_right(){
  mirror([1,0,0]) camera_mount_left();
}

module tripod_clamp_half(is_top=true){
  // Two-piece clamp around beam, with 1/4-20 nut capture in bottom half
  outer_w = BEAM_W + 2*CLAMP_PAD;
  outer_h = BEAM_H + 2*CLAMP_PAD;

  z0 = is_top ? 0 : -outer_h/2;
  zh = outer_h/2;

  difference(){
    // half block
    translate([-CLAMP_LEN/2, -outer_w/2, z0])
      cube([CLAMP_LEN, outer_w, zh], center=false);

    // beam cavity (centered around origin)
    translate([-CLAMP_LEN/2 - 0.5, -(BEAM_W/2 + CLAMP_CLR), -(BEAM_H/2 + CLAMP_CLR)])
      cube([CLAMP_LEN+1, BEAM_W + 2*CLAMP_CLR, BEAM_H + 2*CLAMP_CLR], center=false);

    // clamp bolt pattern (4 bolts), axis along Z
    for (xpos = [-18, 18]){
      for (ypos = [-(BEAM_W/2 + CLAMP_PAD*0.65), (BEAM_W/2 + CLAMP_PAD*0.65)]){
        translate([xpos, ypos, z0 + zh/2])
          cylinder(d=M4_CLR, h=zh+1, center=true);

        // nut traps only in bottom half
        if (!is_top){
          translate([xpos, ypos, z0 + 2.2])
            hex_prism(M4_NUT_AF, M4_NUT_T+0.8);
        }

        // counterbore heads in top half
        if (is_top){
          translate([xpos, ypos, z0 + zh - (M4_HEAD_H/2)])
            cylinder(d=M4_HEAD_D, h=M4_HEAD_H+0.3, center=true);
        }
      }
    }

    // tripod nut trap (bottom half only), axis vertical (Z)
    if (!is_top){
      translate([0, 0, z0 + 2.8])
        hex_prism(QTR_NUT_AF, QTR_NUT_T+1.0);

      // through hole for tripod screw
      translate([0, 0, z0 - 1])
        cylinder(d=QTR_CLR, h=zh+outer_h+2, center=false);
    }
  }
}

module tripod_top(){ tripod_clamp_half(true); }
module tripod_bottom(){ tripod_clamp_half(false); }

// -------------------- Render selector --------------------
if (PART == "segment") segment();
else if (PART == "key") key();
else if (PART == "camera_mount_left") camera_mount_left();
else if (PART == "camera_mount_right") camera_mount_right();
else if (PART == "tripod_top") tripod_top();
else if (PART == "tripod_bottom") tripod_bottom();
else segment();
```
