const express = require('express');
const os = require('os');
const fs = require('fs');
const { exec } = require('child_process');
const app = express();
const port = 5000;

// Enable CORS for all routes
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*'); // Adjust this in production for specific origins
  res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept');
  next();
});

app.get('/', (req, res) => {
  res.send('Backend server is running!');
});

app.get('/api/network-info', (req, res) => {
  const networkInterfaces = os.networkInterfaces();
  const detailedNetworkInfo = {};

  for (const interfaceName in networkInterfaces) {
    const interfaces = networkInterfaces[interfaceName];
    detailedNetworkInfo[interfaceName] = interfaces.map(iface => ({
      address: iface.address,
      netmask: iface.netmask,
      family: iface.family,
      mac: iface.mac,
      internal: iface.internal,
      cidr: iface.cidr,
      scopeid: iface.scopeid // For IPv6
    }));
  }
  res.json(detailedNetworkInfo);
});

// Helper function to parse dhcpd -dumplease output
function parseDhcpdLeaseOutput(output) {
  const leases = [];
  const leaseBlocks = output.split(/lease6\s+([^\{]+)\s*\{/g).filter(Boolean);

  leaseBlocks.forEach(block => {
    const ipMatch = block.match(/ia-na\s+\S+\s*\{\s*starts\s+\S+;\s*ends\s+\S+;\s*iaaddr\s+([^;]+);/);
    const clientHardwareMatch = block.match(/client-id\s+([^;]+);/);
    const hostnameMatch = block.match(/set\s+hostname\s+=\s+"([^"]+)";/);
    const startsMatch = block.match(/starts\s+([^;]+);/);
    const endsMatch = block.match(/ends\s+([^;]+);/);
    const clttMatch = block.match(/cltt\s+([^;]+);/);

    if (ipMatch) {
      leases.push({
        ip_address: ipMatch[1].trim(),
        client_id: clientHardwareMatch ? clientHardwareMatch[1].trim() : 'N/A',
        hostname: hostnameMatch ? hostnameMatch[1].trim() : 'N/A',
        starts: startsMatch ? startsMatch[1].trim() : 'N/A',
        ends: endsMatch ? endsMatch[1].trim() : 'N/A',
        cltt: clttMatch ? clttMatch[1].trim() : 'N/A',
        rawBlock: block.trim() // Keep raw block for debugging if needed
      });
    }
  });
  return leases;
}


app.get('/api/dhcpv6-leases', (req, res) => {
  const dhcpv6LeasePath = '/var/lib/dhcp/dhcpd6.leases';

  fs.access(dhcpv6LeasePath, fs.constants.F_OK, (err) => {
    if (err) {
      // File does not exist
      return res.status(404).json({ error: 'DHCPv6 lease file not found at expected path.', path: dhcpv6LeasePath });
    }

    // Attempt to read the file directly first
    fs.readFile(dhcpv6LeasePath, 'utf8', (readErr, data) => {
      if (!readErr && data.includes('lease6')) { // Simple check if it looks like a readable lease file
        try {
          const leases = parseDhcpdLeaseOutput(data);
          return res.json({ leases, source: 'direct_read' });
        } catch (parseError) {
          console.warn('Direct parsing failed, attempting dhcpd -dumplease:', parseError);
          // Fallback to dhcpd -dumplease if direct parsing fails
        }
      }

      // If direct read failed or parsing failed, try dhcpd -dumplease
      exec(`dhcpd -dumplease < ${dhcpv6LeasePath}`, (execErr, stdout, stderr) => {
        if (execErr) {
          console.error(`exec error: ${execErr}`);
          return res.status(500).json({ error: 'Failed to execute dhcpd -dumplease.', details: execErr.message, stderr });
        }
        if (stderr) {
          console.warn(`dhcpd -dumplease stderr: ${stderr}`);
        }

        try {
          const leases = parseDhcpdLeaseOutput(stdout);
          res.json({ leases, source: 'dhcpd_dumplease' });
        } catch (parseError) {
          console.error('Failed to parse dhcpd -dumplease output:', parseError);
          res.status(500).json({ error: 'Failed to parse dhcpd -dumplease output.', details: parseError.message, rawOutput: stdout });
        }
      });
    });
  });
});

// Helper function to parse dhcpd.leases (DHCPv4) output
function parseDhcpdLeasesV4(output) {
  const leases = [];
  const leaseBlocks = output.split(/lease\s+([^\{]+)\s*\{/g).filter(Boolean);

  leaseBlocks.forEach(block => {
    const ip_address = block.split(/\s+/)[0].trim();
    const startsMatch = block.match(/starts\s+\d+\s+([^;]+);/);
    const endsMatch = block.match(/ends\s+\d+\s+([^;]+);/);
    const clttMatch = block.match(/cltt\s+\d+\s+([^;]+);/);
    const bindingStateMatch = block.match(/binding state\s+([^;]+);/);
    const hardwareEthernetMatch = block.match(/hardware ethernet\s+([^;]+);/);
    const clientHostnameMatch = block.match(/client-hostname\s+"([^"]+)";/);

    if (ip_address) {
      leases.push({
        ip_address: ip_address,
        starts: startsMatch ? startsMatch[1].trim() : 'N/A',
        ends: endsMatch ? endsMatch[1].trim() : 'N/A',
        cltt: clttMatch ? clttMatch[1].trim() : 'N/A',
        binding_state: bindingStateMatch ? bindingStateMatch[1].trim() : 'N/A',
        mac_address: hardwareEthernetMatch ? hardwareEthernetMatch[1].trim() : 'N/A',
        hostname: clientHostnameMatch ? clientHostnameMatch[1].trim() : 'N/A',
      });
    }
  });
  return leases;
}

app.get('/api/dhcpv4-leases', (req, res) => {
  const dhcpv4LeasePath = './zt-taipei-services/dhcp/dhcpd.leases'; // Path to our dummy file

  fs.readFile(dhcpv4LeasePath, 'utf8', (readErr, data) => {
    if (readErr) {
      console.error('Failed to read DHCPv4 lease file:', readErr);
      return res.status(500).json({ error: 'Failed to read DHCPv4 lease file.', details: readErr.message });
    }

    try {
      const leases = parseDhcpdLeasesV4(data);
      res.json({ leases });
    } catch (parseError) {
      console.error('Failed to parse DHCPv4 lease file:', parseError);
      res.status(500).json({ error: 'Failed to parse DHCPv4 lease file.', details: parseError.message });
    }
  });
});

app.listen(port, () => {
  console.log(`Server listening at http://localhost:${port}`);
});
