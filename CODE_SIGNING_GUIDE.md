# Code Signing Guide for PitchTracker

## Overview

Code signing adds a digital signature to your installer that:
- **Removes "Unknown Publisher" warning** during installation
- **Builds trust** with users
- **Prevents tampering** - users know the file hasn't been modified
- **Enables SmartScreen reputation** over time

## Why Code Sign?

### Without Code Signing (Current State)
When users download and run `PitchTracker-Setup-v1.0.0.exe`:
- Windows SmartScreen shows: **"Windows protected your PC"**
- Publisher shows: **"Unknown Publisher"**
- Users must click "More info" → "Run anyway"
- May trigger antivirus false positives

### With Code Signing
- Installer shows: **"Publisher: PitchTracker Development Team"** (or your name)
- No SmartScreen warning (after building reputation)
- Professional appearance
- Users trust the download

## Code Signing Certificate Options

### 1. Standard Code Signing Certificate (EV not required)

**Cost:** $100-$300/year

**Providers:**
- **Sectigo (formerly Comodo)** - $100-$150/year
- **DigiCert** - $300+/year
- **SSL.com** - $150-$200/year
- **GlobalSign** - $200+/year

**Process:**
1. Purchase certificate
2. Verify identity (business or individual)
3. Receive certificate (.pfx file)
4. Sign installer using SignTool.exe

**Pros:**
- Affordable
- Good for individual developers or small projects
- No hardware token required

**Cons:**
- Still shows SmartScreen warning initially (until reputation built)
- Requires annual renewal
- Less trusted than EV certificates

### 2. Extended Validation (EV) Code Signing Certificate

**Cost:** $300-$500/year

**Providers:**
- **DigiCert** - $400+/year
- **Sectigo** - $300+/year
- **SSL.com** - $350+/year

**Process:**
1. Purchase certificate
2. Extensive identity verification (business only, typically)
3. Receive USB hardware token (required)
4. Sign installer using SignTool.exe with token

**Pros:**
- **No SmartScreen warning** from day one
- Highest trust level
- Required for kernel-mode drivers

**Cons:**
- More expensive
- Requires business entity (LLC, Corporation)
- Extensive verification process (2-5 business days)
- Requires USB hardware token (can't be copied/backed up)

### 3. Free Options (Not Recommended for Production)

**Self-Signed Certificate:**
- Cost: Free
- Process: Use PowerShell New-SelfSignedCertificate
- **Problem:** Users must manually trust the certificate
- **Use case:** Internal testing only

**Open Source Program (if applicable):**
- Some certificate authorities offer free certificates for open-source projects
- Example: Certum offers free certs for open-source developers
- **Requirements:** Project must be open-source with visible repository

## Recommendation for PitchTracker

### Option A: Standard Code Signing ($100-$150/year)
**Best for:**
- Individual developer or small team
- Limited budget
- Willing to build SmartScreen reputation over time

**Recommended Provider:** Sectigo (formerly Comodo)
- $100-$150/year
- Good reputation
- Easy process
- Works for individual developers

### Option B: EV Code Signing ($300-$400/year)
**Best for:**
- Professional/commercial product
- Want zero SmartScreen warnings
- Have a business entity (LLC, etc.)
- Budget allows

**Recommended Provider:** DigiCert or Sectigo
- Industry standard
- Immediate SmartScreen bypass
- USB token included

### Option C: Wait (Free)
**Best for:**
- Testing/beta phase
- Very limited distribution
- Budget constraints

**Strategy:**
- Distribute unsigned installer
- Build user base
- Purchase certificate when ready for wider release

## Signing Process

### Prerequisites
- Windows SDK (includes SignTool.exe)
- Code signing certificate (.pfx file)
- Private key password

### Step 1: Install Windows SDK

```powershell
# Download Windows SDK from:
# https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/

# Or install just SignTool via Chocolatey:
choco install windows-sdk-10.0
```

### Step 2: Sign the Installer

```powershell
# Set paths
$signtool = "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe"
$installer = "installer_output\PitchTracker-Setup-v1.0.0.exe"
$cert = "path\to\certificate.pfx"
$password = "your_cert_password"

# Sign the installer
& $signtool sign `
    /f $cert `
    /p $password `
    /tr http://timestamp.digicert.com `
    /td SHA256 `
    /fd SHA256 `
    /d "PitchTracker" `
    /du "https://github.com/berginj/PitchTracker" `
    $installer

# Verify signature
& $signtool verify /pa $installer
```

### Step 3: Integrate into Build Script

Add to `build_installer.ps1`:

```powershell
# After Inno Setup completes...

# Sign the installer
if (Test-Path $CertPath) {
    Write-Host "[5/5] Signing installer..." -ForegroundColor Yellow

    $signtool = "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe"
    $installerPath = "installer_output\PitchTracker-Setup-v$AppVersion.exe"

    & $signtool sign `
        /f $CertPath `
        /p $CertPassword `
        /tr http://timestamp.digicert.com `
        /td SHA256 `
        /fd SHA256 `
        /d "PitchTracker" `
        /du "https://github.com/berginj/PitchTracker" `
        $installerPath

    Write-Host "  ✓ Installer signed" -ForegroundColor Green
} else {
    Write-Host "  Warning: Code signing certificate not found (installer unsigned)" -ForegroundColor Yellow
}
```

## Certificate Storage Best Practices

### Security Recommendations

1. **Never commit certificate to git**
   - Add to `.gitignore`: `*.pfx`, `*.p12`

2. **Store securely**
   - Windows Certificate Store (recommended)
   - Password-protected folder
   - Cloud secrets manager (Azure Key Vault, AWS Secrets Manager)

3. **Backup certificate**
   - Keep multiple backups in secure locations
   - If lost, must purchase new certificate

4. **Protect private key**
   - Use strong password
   - Don't share certificate file
   - Rotate password annually

### Environment Variables Approach

```powershell
# Set environment variables (once)
$env:PITCHTRACKER_CERT_PATH = "C:\Certificates\pitchtracker.pfx"
$env:PITCHTRACKER_CERT_PASSWORD = "strong_password_here"

# Use in build script
$certPath = $env:PITCHTRACKER_CERT_PATH
$certPassword = $env:PITCHTRACKER_CERT_PASSWORD
```

## Timestamping

**Critical:** Always use timestamping when signing!

```powershell
/tr http://timestamp.digicert.com
```

**Why?**
- Allows signature to remain valid after certificate expires
- Proves signing occurred while certificate was valid
- Users can install your software years later

**Timestamp Servers:**
- DigiCert: `http://timestamp.digicert.com`
- Sectigo: `http://timestamp.sectigo.com`
- GlobalSign: `http://timestamp.globalsign.com`

## Building SmartScreen Reputation

Even with a standard (non-EV) certificate, you'll initially see SmartScreen warnings.

### How to Build Reputation:

1. **Time** - Takes 3-6 months of downloads
2. **Volume** - Need significant number of downloads (hundreds+)
3. **No malware reports** - Stay clean
4. **Consistent publisher** - Use same certificate

### Monitoring Reputation:

```powershell
# Check file reputation (requires Windows Defender)
Get-MpThreat | Where-Object Resources -like "*PitchTracker*"
```

## Cost-Benefit Analysis

### Without Code Signing
**Pros:**
- No cost
- No maintenance

**Cons:**
- "Unknown Publisher" warning
- Users hesitant to install
- May trigger antivirus
- Unprofessional appearance

**Recommendation:** OK for beta/internal testing

### With Standard Code Signing ($100-150/year)
**Pros:**
- Shows publisher name
- Professional appearance
- Prevents tampering
- Builds trust

**Cons:**
- Annual cost
- Initial SmartScreen warnings
- Requires maintenance

**Recommendation:** Good for v1.0 release

### With EV Code Signing ($300-400/year)
**Pros:**
- No SmartScreen warnings from day one
- Highest trust
- Professional reputation

**Cons:**
- Higher cost
- Requires business entity
- USB hardware token

**Recommendation:** Best for commercial product

## Getting Started

### For Individual Developer (Recommended):

1. **Purchase Sectigo Standard Code Signing Certificate**
   - Go to: https://comodosslstore.com/code-signing
   - Select "Standard Code Signing Certificate"
   - Cost: ~$100-$150/year

2. **Verification Process**
   - Provide government ID
   - Verify email/phone
   - 1-3 business days

3. **Receive Certificate**
   - Download .pfx file
   - Store securely with password

4. **Install Windows SDK**
   - Download from Microsoft
   - Or: `choco install windows-sdk-10.0`

5. **Sign Installer**
   - Use SignTool.exe command above
   - Test installation

6. **Integrate into Build**
   - Update build_installer.ps1
   - Add certificate path to environment variables

### For Business Entity:

1. **Purchase EV Code Signing Certificate**
   - DigiCert or Sectigo
   - Cost: ~$300-$400/year

2. **Business Verification**
   - Provide business registration documents
   - Verify business address
   - 3-5 business days

3. **Receive USB Token**
   - Physical hardware token shipped
   - Cannot be backed up (hardware-bound)

4. **Sign with Token**
   - Insert USB token
   - Use SignTool with token reference

## Alternatives to Consider

### 1. Microsoft Store Distribution
- No code signing needed (Microsoft signs)
- Automatic updates
- Trusted by Windows
- **Cons:** Microsoft app requirements, review process

### 2. ClickOnce Deployment
- Self-updating deployment
- Can use standard certificates
- **Cons:** More complex setup

### 3. Build Reputation First
- Distribute unsigned initially
- Gather feedback from trusted users
- Purchase certificate once user base established
- **Benefit:** Ensures project viability before investing

## Timeline for Implementation

**Immediate (Now):**
- Continue distributing unsigned installer
- Document this guide for future reference
- Monitor user feedback

**Short-term (1-3 months):**
- If positive user reception, purchase standard certificate
- Sign installer for v1.1.0 or v1.2.0
- Start building SmartScreen reputation

**Long-term (6-12 months):**
- Consider upgrading to EV certificate
- Form business entity if needed
- Professional reputation established

## Testing Signed Installer

After signing:

1. **Verify Signature:**
   ```powershell
   Get-AuthenticodeSignature installer_output\PitchTracker-Setup-v1.0.0.exe
   ```

2. **Check Properties:**
   - Right-click installer
   - Properties → Digital Signatures tab
   - Should show your name/organization

3. **Test Installation:**
   - Fresh Windows 10/11 VM
   - Download installer
   - Run installer
   - Check for warnings

4. **Monitor SmartScreen:**
   - May still show warning initially
   - Improves over time with downloads

## Resources

**Certificate Authorities:**
- Sectigo: https://sectigo.com/ssl-certificates-tls/code-signing
- DigiCert: https://www.digicert.com/signing/code-signing-certificates
- SSL.com: https://www.ssl.com/certificates/code-signing/

**Tools:**
- Windows SDK (SignTool): https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/
- SignTool Documentation: https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool

**Guides:**
- Code Signing Best Practices: https://learn.microsoft.com/en-us/windows-hardware/drivers/install/code-signing-best-practices
- SmartScreen Reputation: https://learn.microsoft.com/en-us/windows/security/threat-protection/windows-defender-smartscreen/windows-defender-smartscreen-overview

---

## Next Steps

1. **Decide on timing** - Now vs. after initial release
2. **Choose certificate type** - Standard vs. EV
3. **Select provider** - Sectigo recommended for individuals
4. **Purchase certificate** - Allow 1-3 days for verification
5. **Install and test** - Sign a test build
6. **Integrate into build** - Update build_installer.ps1
7. **Monitor reputation** - Track SmartScreen warnings over time

**Questions?** Check with certificate authority support or Microsoft documentation.
