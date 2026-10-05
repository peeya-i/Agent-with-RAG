"""Data generator for 100 product offerings with tiered volume pricing:
- Qty 1: Base Price
- Qty 10+: 10% discount (0.90 * Base Price)
- Qty 100+: 30% discount (0.70 * Base Price)
"""

def get_product_catalog_data():
    raw_products = [
        # Cloud & AI Compute (1-15)
        ("PRD-001", "Nexus AI Inference Accelerator Card", "Enterprise PCIe Gen5 neural compute accelerator with 48GB HBM3 memory for ultra-low latency LLM inference.", 2499.00),
        ("PRD-002", "VectorMesh High-Density GPU Blade", "Dual-socket liquid-cooled server blade hosting 8x Tensor Core GPUs optimized for high-dimensional vector search.", 18500.00),
        ("PRD-003", "Apex Edge AI Gateway Mini", "Ruggedized fanless industrial edge processor running local quantized transformer models in harsh field environments.", 850.00),
        ("PRD-004", "Cognitive Server Appliance 2U", "Turnkey rackmount 2U server preconfigured with Ollama and FastMCP tool execution runtime clusters.", 7200.00),
        ("PRD-005", "Quantum-Safe Cryptographic Coprocessor", "Hardware security PCIe module providing post-quantum lattice cryptography and deterministic key signing.", 3150.00),
        ("PRD-006", "Neural Engine Micro-Module", "Embedded low-power system-on-chip for real-time sensor processing and on-device tokenization.", 280.00),
        ("PRD-007", "HyperCompute AI Workstation Max", "Desktop liquid-cooled workstation with 128GB unified VRAM, dual 100GbE NICs, and enterprise Linux OS.", 9800.00),
        ("PRD-008", "TensorCore Matrix Acceleration Unit", "Dedicated matrix arithmetic accelerator for deep learning training and high-throughput embedding calculations.", 4200.00),
        ("PRD-009", "CloudNode Multi-Tenant Server", "High-density multi-tenant cloud compute node with hardware memory encryption and SR-IOV virtualization.", 6400.00),
        ("PRD-010", "EdgeVector Compact Gateway", "Field-deployable vector database gateway with built-in 4G/5G failover and local ChromaDB persistence.", 1150.00),
        ("PRD-011", "Autonomous Robotics Compute Brain", "IP67-rated embedded robotic controller with dual cameras and real-time motion planning neural network.", 3600.00),
        ("PRD-012", "MicroCluster AI Server Cube", "Compact cube clustering unit combining 4 compute nodes with shared NVLink interconnect for lab testing.", 5400.00),
        ("PRD-013", "Neuromorphic Spike Processing Board", "Bio-inspired event-based neural processing board with sub-1ms response times for temporal pattern detection.", 1890.00),
        ("PRD-014", "DeepLearning Cloud Accelerator Pod", "Modular 4U compute expansion chassis delivering 2 PFLOPS of FP16 tensor performance.", 24500.00),
        ("PRD-015", "Quantum Random Number Generator Card", "High-throughput true physical quantum entropy PCIe card generating 1 Gbps of unguessable random seed keys.", 1650.00),

        # Networking & Telecommunications (16-30)
        ("PRD-016", "Nexus 400GbE Spine Data Switch", "Ultra-low latency 32-port 400GbE QSFP-DD Layer 3 data center switch with telemetry and RoCE v2 support.", 14200.00),
        ("PRD-017", "Enterprise 100GbE Leaf Switch 48-Port", "High-density 48x 100GbE SFP28 leaf switch with redundant power supplies and line-rate hardware buffering.", 8900.00),
        ("PRD-018", "Zero-Latency Fiber Transceiver 400G", "Single-mode optical transceiver supporting 400GBASE-LR4 over duplex single-mode fiber up to 10km.", 650.00),
        ("PRD-019", "Industrial Ruggedized 10GbE Switch", "DIN-rail mounted managed 8-port 10GbE Ethernet switch designed for wide-temperature factory automation.", 1450.00),
        ("PRD-020", "Multi-Tenant Edge SD-WAN Gateway", "Intelligent software-defined WAN gateway with automated traffic steering, IPsec VPN, and zero-touch setup.", 2100.00),
        ("PRD-021", "Direct-Attach Copper Cable 100G 2m", "High-speed passive twinaxial copper cable assembly for intra-rack server-to-switch interconnects.", 85.00),
        ("PRD-022", "Active Optical Cable 400G 10m", "Lightweight plenum-rated active optical breakout cable delivering high bandwidth with low EMI noise.", 340.00),
        ("PRD-023", "Carrier-Grade Core Border Router", "Modular multi-terabit perimeter core router with redundant routing engines and BGP flow-spec defense.", 28000.00),
        ("PRD-024", "Wireless Access Point Wi-Fi 7 Enterprise", "Tri-band Wi-Fi 7 access point with 4x4 MU-MIMO, beamforming, and dedicated WPA3 enterprise security.", 780.00),
        ("PRD-025", "Hardware Network Packet Broker 1U", "High-density packet inspection broker aggregating and filtering network traffic for IDS/IPS telemetry taps.", 4950.00),
        ("PRD-026", "Cellular 5G Enterprise Gateway Hub", "Dual-SIM 5G/LTE industrial bridge with high-gain directional MIMO antennas and PoE power pass-through.", 1250.00),
        ("PRD-027", "High-Speed Patch Panel Cat6A 48-Port", "Shielded 1U 19-inch modular RJ45 keystone patch panel for enterprise structured network cabling.", 195.00),
        ("PRD-028", "Fiber Optic Enclosure 1U Rackmount", "Sliding fiber distribution patch panel with LC duplex couplers supporting up to 96 strands of OS2 fiber.", 320.00),
        ("PRD-029", "Console Server 16-Port Out-of-Band", "Secure serial terminal server providing out-of-band remote console management with integrated 4G backup.", 1680.00),
        ("PRD-030", "Network Precision Time Protocol Server", "GNSS-synchronized IEEE 1588 PTP grandmaster clock delivering sub-nanosecond time stamps to clusters.", 3850.00),

        # Storage & Backup Architecture (31-45)
        ("PRD-031", "Nexus All-Flash NVMe Array 30TB", "Dual-controller enterprise NVMe storage appliance delivering 1.2M IOPS and 100GbE NVMe-oF connectivity.", 16800.00),
        ("PRD-032", "Enterprise NVMe SSD U.2 15.36TB", "High-endurance PCIe 4.0 enterprise solid-state drive with power loss protection and 1 DWPD reliability.", 1850.00),
        ("PRD-033", "Enterprise NVMe SSD U.2 7.68TB", "Read-intensive enterprise solid-state drive optimized for ChromaDB vector embeddings and read caches.", 980.00),
        ("PRD-034", "High-Capacity SAS HDD 24TB 7.2K", "Helium-sealed 12Gb/s SAS enterprise hard drive designed for high-density cold document storage arrays.", 460.00),
        ("PRD-035", "Hybrid SAN/NAS Storage Appliance 4U", "Unified storage controller with 24 hot-swap bays, dual 10GbE SFP+ ports, and ZFS replication.", 11200.00),
        ("PRD-036", "LTO-9 Tape Autoloader 24-Slot", "Automated magnetic tape backup library supporting 432TB raw storage with hardware AES-256 encryption.", 7400.00),
        ("PRD-037", "LTO-9 Ultrium Tape Cartridge 18TB", "High-density barium ferrite magnetic data cartridge providing 30-year archival media longevity.", 145.00),
        ("PRD-038", "Hardware RAID Controller 12Gb/s SAS", "PCIe 4.0 Tri-Mode RAID controller with 8GB onboard flash cache and battery backup power unit.", 820.00),
        ("PRD-039", "PCIe Gen5 NVMe AIC Expansion 64TB", "Full-height add-in card aggregating 4x M.2 NVMe drives into a single ultra-fast storage volume.", 6200.00),
        ("PRD-040", "Immutable WORM Storage Gateway", "Dedicated compliance gateway enforcing strict Write-Once-Read-Many retention policies for SEC filings.", 5300.00),
        ("PRD-041", "Direct-Attached Storage (DAS) 2U 12-Bay", "High-speed JBOD expansion shelf with 12Gb/s SAS-3 dual expander modules for clustered storage nodes.", 3100.00),
        ("PRD-042", "NVMe-oF Bridge Adapter Card 100GbE", "Host channel adapter offloading RDMA-over-Converged-Ethernet storage protocols at line rate.", 1150.00),
        ("PRD-043", "Industrial M.2 NVMe SSD 2TB", "Wide-temperature (-40C to +85C) M.2 NVMe storage drive with conformal coating for rugged IoT nodes.", 340.00),
        ("PRD-044", "High-Density Object Storage Server 60-Bay", "Top-loading 4U bulk storage server chassis accommodating 60x 3.5-inch SAS drives for petabyte scale.", 19500.00),
        ("PRD-045", "Disaster Recovery Replication Appliance", "Hardware appliance executing continuous delta-block replication and automated vector database failover.", 8600.00),

        # Security & Identity Perimeter (46-60)
        ("PRD-046", "Next-Gen Enterprise Firewall 40Gbps", "Deep packet inspection firewall appliance with AI threat prevention, SSL inspection, and multi-tenant zoning.", 12500.00),
        ("PRD-047", "Hardware Security Module (HSM) FIPS 140-3", "Tamper-responsive dedicated cryptographic appliance for enterprise root CA keys and JWT signing secrets.", 18900.00),
        ("PRD-048", "Biometric Access Terminal Pro", "Facial recognition and fingerprint scanner with anti-spoofing liveness detection and Wiegand controller.", 920.00),
        ("PRD-049", "Smart Card Enterprise Token (Pack of 25)", "FIPS 201 compliant dual-interface contact and contactless PIV smart cards for two-factor authentication.", 375.00),
        ("PRD-050", "Hardware Security Key FIDO2/WebAuthn", "USB-C and NFC physical security authenticator with fingerprint sensor for passwordless agent access.", 75.00),
        ("PRD-051", "Enterprise Web Application Firewall (WAF)", "Dedicated hardware WAF providing OWASP Top 10 mitigation, rate limiting, and prompt injection defense.", 6800.00),
        ("PRD-052", "Intrusion Detection/Prevention Sensor 1U", "Real-time network security sensor monitoring deep traffic patterns for lateral movement and exfiltration.", 5400.00),
        ("PRD-053", "Privileged Access Management (PAM) Vault", "Isolated secure hardware appliance storing service passwords, SSH private keys, and container secrets.", 8100.00),
        ("PRD-054", "Physical Security Door Controller 4-Door", "Networked access control panel supporting 4 card readers, auxiliary inputs, and electric strike relays.", 640.00),
        ("PRD-055", "Tamper-Evident Security Seal (Pack of 500)", "Barcoded tamper-indicating serial seals for server racks, shipping containers, and forensic drives.", 160.00),
        ("PRD-056", "SSL/TLS Offloader Acceleration Card", "PCIe cryptography offload accelerator terminating 500,000 concurrent TLS 1.3 connections in hardware.", 2850.00),
        ("PRD-057", "Vulnerability Assessment Appliance", "Rackmount security scanner automatically performing internal port audits and compliance benchmarks.", 4700.00),
        ("PRD-058", "Deception Network Honeypot Node", "Dedicated appliance deploying decoy microservices to detect internal network reconnaissance attempts.", 3200.00),
        ("PRD-059", "Data Loss Prevention (DLP) Network Monitor", "Hardware inspection unit analyzing outbound traffic for unmasked PII, trade secrets, and API credentials.", 6100.00),
        ("PRD-060", "Air-Gapped Optical Data Diode 1Gbps", "Unidirectional hardware optical isolator guaranteeing physically impossible reverse data transmission.", 4900.00),

        # Enterprise Software Licenses & Subscriptions (61-75)
        ("PRD-061", "Nexus Agentic Core Annual License", "Per-node annual enterprise subscription for autonomous multi-turn agent planning, reasoning, and execution.", 4800.00),
        ("PRD-062", "VectorMesh Enterprise Database License", "Annual software license for distributed ChromaDB clustering with cross-region replication and multi-tenancy.", 3600.00),
        ("PRD-063", "Nexus Multi-Tenant Gateway License", "Annual subscription for cryptographic JWT domain routing, role enforcement, and token lifecycle management.", 2400.00),
        ("PRD-064", "FastMCP Procedural Tool Connector Pack", "Annual access license to 50 certified procedural connectors for SAP, Salesforce, Bloomberg, and Oracle.", 1800.00),
        ("PRD-065", "Nexus Sentinel Audit & Compliance Suite", "Comprehensive real-time telemetry logging, token tracking, and forensic replay software license.", 2900.00),
        ("PRD-066", "Ollama Acceleration Enterprise Suite", "GPU-optimized container runtime license for high-throughput local vector embeddings and prompt synthesis.", 1500.00),
        ("PRD-067", "Continuous Threat Intelligence Feed (1-Yr)", "Daily updated threat telemetry feed with automated firewall rule injection and malicious IP blocking.", 2100.00),
        ("PRD-068", "Enterprise Knowledge Ingestion Pipeline SDK", "High-performance document chunking, optical character recognition, and PDF parsing software license.", 1950.00),
        ("PRD-069", "Automated Unit Economics & Billing Module", "Software plugin tracking per-tenant token usage, model inference costs, and custom invoice generation.", 1200.00),
        ("PRD-070", "Synthetic Data Generation Toolkit", "Algorithmic suite for generating privacy-preserving synthetic test data for machine learning model tuning.", 2750.00),
        ("PRD-071", "Nexus Kubernetes Operator Enterprise", "Native Kubernetes controller managing autonomous agent containers, auto-scaling, and rolling updates.", 3200.00),
        ("PRD-072", "High-Availability Clustering Extension", "Active-active multi-datacenter consensus license with zero-RPO data synchronization across nodes.", 4100.00),
        ("PRD-073", "Autonomous Log Analytics Engine", "Machine learning log parser aggregating log.json traces and calculating TTFT, ITL, and TPS metrics.", 2300.00),
        ("PRD-074", "Prompt Safety Guardrail Middleware", "Real-time sanitization proxy preventing jailbreaks, indirect prompt injection, and toxic generations.", 1850.00),
        ("PRD-075", "Enterprise Developer Studio IDE Extension", "Team license for interactive agent prompt debugging, tool testing, and vector similarity heatmaps.", 850.00),

        # IoT, Edge & Environmental Sensing (76-85)
        ("PRD-076", "Industrial IoT Smart Gateway Node", "ARM64 multi-sensor edge hub with Modbus, CAN-bus, RS-485 interfaces, and IP68 sealed aluminum enclosure.", 950.00),
        ("PRD-077", "Precision Temperature/Humidity Sensor", "NIST-traceable digital environmental sensor probe transmitting data over LoRaWAN and Modbus RTU.", 145.00),
        ("PRD-078", "Differential Air Pressure Monitor", "Cleanroom and data center airflow sensor detecting filter degradation and containment pressure drops.", 260.00),
        ("PRD-079", "Acoustic Noise & Vibration Sensor", "High-frequency triaxial accelerometer detecting bearing wear and predictive failure in server fans.", 310.00),
        ("PRD-080", "Infrared Thermal Imaging Sensor Grid", "80x62 pixel radiometric thermal camera sensor monitoring server rack hotspots and electrical panels.", 680.00),
        ("PRD-081", "Water Leak Detection Cable System (50m)", "Continuous conductive polymer sensing cable pinpointing liquid leaks beneath raised data center floors.", 420.00),
        ("PRD-082", "Gas & Smoke Detection Aspirating System", "Very Early Warning Aspirating Smoke Detection (VESDA) unit actively sampling data center air ducts.", 2350.00),
        ("PRD-083", "Power Quality & Current Monitor CT Sensor", "Split-core current transformer sensor measuring True-RMS electrical current, harmonics, and surges.", 185.00),
        ("PRD-084", "Magnetic Door Contact & Tamper Switch", "Supervised dual-contact magnetic reed switch detecting unauthorized physical access to server racks.", 45.00),
        ("PRD-085", "LoRaWAN Long-Range Gateway Base Station", "Outdoor IP67 16-channel LoRaWAN gateway supporting over 10,000 industrial sensors across a 15km radius.", 1650.00),

        # Power, Cooling & Data Center Facilities (86-93)
        ("PRD-086", "Enterprise Online UPS System 10kVA", "Double-conversion online uninterruptible power supply with hot-swappable batteries and SNMP management.", 6200.00),
        ("PRD-087", "Intelligent Switched PDU 30A 24-Outlet", "Zero-U vertical rack power distribution unit with per-outlet metering, remote power cycling, and environmental ports.", 1150.00),
        ("PRD-088", "In-Row Liquid Cooling Chiller Unit", "High-efficiency 30kW in-row closed-loop liquid cooling distribution unit for high-density GPU racks.", 18500.00),
        ("PRD-089", "Server Cabinet 42U Heavy-Duty Enclosure", "Standard 19-inch 42U data center server rack with 80% perforated mesh doors and integrated cable management.", 1450.00),
        ("PRD-090", "Automatic Transfer Switch (ATS) 16A 1U", "Dual-source redundant power transfer switch switching utility to generator power in under 16ms.", 880.00),
        ("PRD-091", "Liquid Immersion Server Tank (4 Nodes)", "Direct immersion cooling tank utilizing dielectric fluid to dissipate up to 100kW of GPU compute heat.", 26500.00),
        ("PRD-092", "Rack Containment Aisle Ceiling Panel Kit", "Thermal containment modular roof panels preventing hot exhaust air mixing with cold supply air aisles.", 780.00),
        ("PRD-093", "Clean Agent Fire Suppression Cylinder (FM-200)", "Pre-engineered clean agent chemical fire extinguishing cylinder safe for electronic equipment and humans.", 3900.00),

        # Autonomous Logistics, Robotics & Workstations (94-100)
        ("PRD-094", "Autonomous Mobile Robot (AMR) 500kg", "Industrial autonomous warehouse transport robot with dual LiDAR, SLAM navigation, and automated charging.", 28500.00),
        ("PRD-095", "Industrial Automated Barcode Sorter Scanner", "High-speed omnidirectional multi-laser bar code reader reading moving parcels on conveyor belts at 3 m/s.", 3400.00),
        ("PRD-096", "Rugged Mobile Data Terminal Android 14", "Mil-Spec drop-resistant handheld enterprise computer with integrated 2D barcode scanner and Wi-Fi 6E.", 1250.00),
        ("PRD-097", "Robotic Arm Pneumatic Gripper End-Effector", "Soft-touch adaptive vacuum gripper picking irregular e-commerce packages and delicate pharmaceuticals.", 2200.00),
        ("PRD-098", "Dual-Display Ergonomic Dev Workstation", "Motorized sit-stand desk integrated with dual 32-inch 4K color-calibrated monitors and cable management.", 1950.00),
        ("PRD-099", "Mechanical Ergonomic Coding Keyboard Pro", "Hot-swappable mechanical split keyboard with programmable macro firmware and USB-C detachable cabling.", 240.00),
        ("PRD-100", "Autonomous Fleet Telematics Edge Box", "Vehicle telematics computer tracking CAN-bus telemetry, GPS coordinates, and refrigeration temperatures.", 650.00),
    ]

    # Calculate tiered volume pricing:
    # Qty 1: Base Price
    # Qty 10: 10% discount -> base * 0.90
    # Qty 100: 30% discount -> base * 0.70
    products = []
    for item_id, name, desc, base_price in raw_products:
        price_1 = float(base_price)
        price_10 = round(price_1 * 0.90, 2)
        price_100 = round(price_1 * 0.70, 2)
        products.append({
            "item_id": item_id,
            "name": name,
            "description": desc,
            "price_1": price_1,
            "price_10": price_10,
            "price_100": price_100
        })

    return products
