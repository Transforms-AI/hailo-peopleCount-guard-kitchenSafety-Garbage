
# **Using DeGirum PySDK, DeGirum Tools, and Hailo Hardware**  

This repository provides a comprehensive guide on using **DeGirum PySDK**, **DeGirum Tools**, and **Hailo hardware** for efficient AI inference. These tools simplify edge AI development by enabling seamless integration, testing, and deployment of AI models on multiple hardware platforms, including **Hailo-8** and **Hailo-8L**.  

---
## **Table of Contents**

### Automatic setup
1. [Setup script - Automatic setup](#setup-script---automatic-setup)
2. [Change config file](#change-config-file)
3. [Run Model](#run_model)

### Manual setup
1. [Setting up your raspberry pi](#setting-up-your-raspberry-pi)
2. [Prerequisites](#prerequisites)  
3. [Installation](#installation)  
4. [Resources download](#download-models-and-demo-video)
5. [Degirum sources](#additional-resources) 

# Automatic setup
## Setup script - Automatic setup
Run this script, this will do the rest. take this setup-script.sh to any raspberry pi you wnat to setup. And then run the bash command

First make the setup-script.sh executabel
```bash
chmod +x setup-script.sh
```
then run this
```bash
bash ./setup-script.sh
```
This script will do these things-
1. Configure raspberry pi for PCIe Gen3 speed
2. Setup raspberry pi with hailo and hailort
3. Git clone this repo
4. Create a virtual env and activate
5. Install requirements
6. Install hailort whl in the venv
7. Create a post_reboot script and config it to run only once and self delete after that
8. Automatically reboots
9. After reboot automatically runs the post_reboot script on background. you can see the output in ~$hailort.log
10. post_reboot checks if everything is okay, if the below error is found Then fixes it automatically.
```bash
[HailoRT] [error] CHECK failed - Driver version (4.18.0) is different from library version (4.20.0)
[HailoRT] [error] Driver version mismatch, status HAILO_INVALID_DRIVER_VERSION(76)
```
11. If everything OK. post_processor slef distructs
12. Takes another reboot.
13. Now the system is ready to run models.
  

If any problem arises you can simply use the manual step.

## Change config file
To check the output stream on the website, you have to config the local ip and sn. You shall find all the config in config dir.
from 
```bash
cd hailo-peopleCount-guard-kitchenSafety-Garbage/config/config_guard_detection.json
```
Change this lines accordingly
```bash
"sn" : "HEADCOUNT1"
# and to your device ip
"local_ip": "192.168.8.101"
```

## Run Model
After changing the config you have to activate the venv and run the model using 
```bash
bash ./run_detection.sh
```
---

# **Manual Setup**

## **Setting up your raspberry pi**
If using for the first time.

run this commands first

```bash
sudo apt update && sudo apt full-upgrade
sudo rpi-eeprom-update
```
We need to change some PCIe settings if using Hailo Ai kit. Ai kit is the one that is conncected via M.2 slot. There is another version Hailo Ai hat, the hailo chip is baked in the Ai hat curcuit. 

The Ai kit/Ai hat should be connected to your raspberry Pi.

Run the following command to open the Raspberry Pi Configuration CLI:

```bash
sudo raspi-config
```

Complete the following steps to enable PCIe Gen 3.0 speeds:

1. Select ```Advanced Options```.

2. Select ```PCIe Speed```.

3. Choose ```Yes``` to enable PCIe Gen 3 mode.

4. Select ```Finish``` to exit.

Reboot your Raspberry Pi with ```sudo reboot``` for your changes to take effect.

There is another way.
To enable PCIe Gen 3.0 speeds, add the following line to /boot/firmware/config.txt:
```bash
dtparam=pciex1_gen=3
```
Reboot your Raspberry Pi with sudo reboot for these settings to take effect.



## **Prerequisites**  

- **Hailo Tools Installed**: Ensure that Hailo's tools and SDK are properly installed and configured. For reference here's  [Hailo's documentation](https://hailo.ai/) 

  So, lets install them, just run the commands below.

  ```bash
  sudo apt install hailo-all
  ```

  To ensure everything is running correctly, run the following command:
  ```bash
  hailortcli fw-control identify
  ```

- **Hailo Runtime Install**:  
  DeGirum PySDK supports **Hailo Runtime versions 4.19.0 and 4.20.0**. So, We need to Install them, run the commands below:

  ```bash
  sudo apt install python3-hailort
  ```
  Also, enable the HailoRT Multi-Process service as per HailoRT documentation:  

  ```bash
  sudo systemctl enable --now hailort.service  # for Ubuntu
  ```  

  You have to also download the hailort wheel and install it in your virtual environment. We will do it in the installations section later.

- **Python 3.11**: Ensure Python is installed on your system. You can check your Python version using:  

  ```bash
  python3 --version
  ```  

---

## **Installation**  

The best way to get started is to **clone this repository** and set up a virtual environment to keep dependencies organized. Follow these steps:  

### **1. Clone the Repository**  
Clone this git repo in your raspberry pi
```bash
git clone https://github.com/Transforms-AI/hailo-peopleCount-guard-kitchenSafety-Garbage.git
cd hailo-peopleCount-guard-kitchenSafety-Garbage
```

### **2. Create a Virtual Environment**  
To keep the Python environment isolated, create a virtual environment and activate it: 

```bash
python3 -m venv degirum_env
source degirum_env/bin/activate
```  

### **3. Install Required Dependencies**  
Install all necessary packages from `requirements.txt`:  

```bash
pip install -r requirements.txt
```  
We will also have to downlaod the hailort or Hailo Runtime wheel in the virtual environment.
First download the  hailort-4.20.0-cp311-cp311-linux_aarch64.whl
```bash
gdown "https://drive.google.com/uc?id=1NrRxzcMc45nQ4_nnoOd1xiU0o8e3EOUo"
```
Now install it in your virtual environment
```bash
pip install hailort-4.20.0-cp311-cp311-linux_aarch64.whl
```

---


### **5. Verify Installation**  

To ensure that everything is set up correctly, run the provided test script:  

```bash
python test.py
```  

This script will:  
- Check system information.  
- Verify that Hailo hardware is recognized.  
- Load and run inference with a sample AI model.  

If the test runs successfully, your environment is properly configured.  



## Download Models and demo video
activate the virtual environment the run this to get all the models and test video. The git repo will not have any models. If you are using the automatic scipt 

```bash
bash ./download.sh
```
---
## Additional Resources

- [Hailo Model Zoo](./hailo_model_zoo.md): Explore the full list of models optimized for Hailo hardware.
- [DeGirum Documentation](https://docs.degirum.com)
- [Hailo Documentation](https://hailo.ai/)
