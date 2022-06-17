// board enforces
//   in-state
//      accel set/resume
//   out-state
//      cancel button
//      accel rising edge
//      brake rising edge
//      brake > 0mph
const CanMsg HONDA_N_TX_MSGS[] = {{0xE4, 0, 5}, {0x194, 0, 4}, {0x1FA, 0, 8}, {0x200, 0, 6}, {0x30C, 0, 8}, {0x33D, 0, 5}};
const CanMsg HONDA_BG_TX_MSGS[] = {{0xE4, 2, 5}, {0xE5, 2, 8}, {0x296, 0, 4}, {0x33D, 2, 5}};  // Bosch Giraffe
const CanMsg HONDA_BH_TX_MSGS[] = {{0xE4, 0, 5}, {0xE5, 0, 8}, {0x296, 1, 4}, {0x33D, 0, 5}};  // Bosch Harness
const CanMsg HONDA_BG_LONG_TX_MSGS[] = {{0xE4, 0, 5}, {0x1DF, 0, 8}, {0x1EF, 0, 8}, {0x1FA, 0, 8}, {0x30C, 0, 8}, {0x33D, 0, 5}, {0x39F, 0, 8}, {0x18DAB0F1, 0, 8}};  // Bosch Giraffe w/ gas and brakes
const CanMsg HONDA_BH_LONG_TX_MSGS[] = {{0xE4, 1, 5}, {0x1DF, 1, 8}, {0x1EF, 1, 8}, {0x1FA, 1, 8}, {0x30C, 1, 8}, {0x33D, 1, 5}, {0x39F, 1, 8}, {0x18DAB0F1, 1, 8}};  // Bosch Harness w/ gas and brakes

// Roughly calculated using the offsets in openpilot +5%:
// In openpilot: ((gas1_norm + gas2_norm)/2) > 15
// gas_norm1 = ((gain_dbc1*gas1) + offset_dbc)
// gas_norm2 = ((gain_dbc2*gas2) + offset_dbc)
// assuming that 2*(gain_dbc1*gas1) == (gain_dbc2*gas2)
// In this safety: ((gas1 + (gas2/2))/2) > THRESHOLD
const int HONDA_GAS_INTERCEPTOR_THRESHOLD = 344;
#define HONDA_GET_INTERCEPTOR(msg) (((GET_BYTE((msg), 0) << 8) + GET_BYTE((msg), 1) + ((GET_BYTE((msg), 2) << 8) + GET_BYTE((msg), 3)) / 2 ) / 2) // avg between 2 tracks
const int HONDA_BOSCH_NO_GAS_VALUE = -30000; // value sent when not requesting gas
const int HONDA_BOSCH_GAS_MAX = 2000;
const int HONDA_BOSCH_ACCEL_MIN = -350; // max braking == -3.5m/s2

// Nidec and Bosch giraffe have pt on bus 0
AddrCheckStruct honda_rx_checks[] = {
  {.msg = {{0x1A6, 0, 8, .check_checksum = true, .max_counter = 3U, .expected_timestep = 40000U},
           {0x296, 0, 4, .check_checksum = true, .max_counter = 3U, .expected_timestep = 40000U}}},
  {.msg = {{0x158, 0, 8, .check_checksum = true, .max_counter = 3U, .expected_timestep = 10000U}}},
  {.msg = {{0x17C, 0, 8, .check_checksum = true, .max_counter = 3U, .expected_timestep = 10000U}}},
};
const int HONDA_RX_CHECKS_LEN = sizeof(honda_rx_checks) / sizeof(honda_rx_checks[0]);

// Bosch harness has pt on bus 1
AddrCheckStruct honda_bh_rx_checks[] = {
  {.msg = {{0x296, 1, 4, .check_checksum = true, .max_counter = 3U, .expected_timestep = 40000U}}},
  {.msg = {{0x158, 1, 8, .check_checksum = true, .max_counter = 3U, .expected_timestep = 10000U}}},
  {.msg = {{0x17C, 1, 8, .check_checksum = true, .max_counter = 3U, .expected_timestep = 10000U}}},
};
const int HONDA_BH_RX_CHECKS_LEN = sizeof(honda_bh_rx_checks) / sizeof(honda_bh_rx_checks[0]);

const uint16_t HONDA_PARAM_ALT_BRAKE = 1;
const uint16_t HONDA_PARAM_BOSCH_LONG = 2;

int honda_brake = 0;
bool honda_alt_brake_msg = false;
bool honda_fwd_brake = false;
bool honda_bosch_long = false;
enum {HONDA_N_HW, HONDA_BG_HW, HONDA_BH_HW} honda_hw = HONDA_N_HW;


static uint8_t honda_get_checksum(CAN_FIFOMailBox_TypeDef *to_push) {
  int checksum_byte = GET_LEN(to_push) - 1;
  return (uint8_t)(GET_BYTE(to_push, checksum_byte)) & 0xFU;
}

static uint8_t honda_compute_checksum(CAN_FIFOMailBox_TypeDef *to_push) {
  int len = GET_LEN(to_push);
  uint8_t checksum = 0U;
  unsigned int addr = GET_ADDR(to_push);
  while (addr > 0U) {
    checksum += (addr & 0xFU); addr >>= 4;
  }
  for (int j = 0; j < len; j++) {
    uint8_t byte = GET_BYTE(to_push, j);
    checksum += (byte & 0xFU) + (byte >> 4U);
    if (j == (len - 1)) {
      checksum -= (byte & 0xFU);  // remove checksum in message
    }
  }
  return (8U - checksum) & 0xFU;
}

static uint8_t honda_get_counter(CAN_FIFOMailBox_TypeDef *to_push) {
  int counter_byte = GET_LEN(to_push) - 1;
  return ((uint8_t)(GET_BYTE(to_push, counter_byte)) >> 4U) & 0x3U;
}

static int honda_rx_hook(CAN_FIFOMailBox_TypeDef *to_push) {

  bool valid;
  if (honda_hw == HONDA_BH_HW) {
    valid = addr_safety_check(to_push, honda_bh_rx_checks, HONDA_BH_RX_CHECKS_LEN,
                              honda_get_checksum, honda_compute_checksum, honda_get_counter);
  } else {
    valid = addr_safety_check(to_push, honda_rx_checks, HONDA_RX_CHECKS_LEN,
                              honda_get_checksum, honda_compute_checksum, honda_get_counter);
  }

  if (valid) {
    int addr = GET_ADDR(to_push);
    int len = GET_LEN(to_push);
    int bus = GET_BUS(to_push);

    // sample speed
    if (addr == 0x158) {
      // first 2 bytes
      vehicle_moving = GET_BYTE(to_push, 0) | GET_BYTE(to_push, 1);
    }

    // state machine to enter and exit controls
    // 0x1A6 for the ILX, 0x296 for the Civic Touring
    if ((addr == 0x1A6) || (addr == 0x296)) {
      int button = (GET_BYTE(to_push, 0) & 0xE0) >> 5;
      switch (button) {
        case 2:  // cancel
          controls_allowed = 0;
          break;
        case 3:  // set
        case 4:  // resume
          controls_allowed = 1;
          break;
        default:
          break; // any other button is irrelevant
      }
    }

    // user brake signal on 0x17C reports applied brake from computer brake on accord
    // and crv, which prevents the usual brake safety from working correctly. these
    // cars have a signal on 0x1BE which only detects user's brake being applied so
    // in these cases, this is used instead.
    // most hondas: 0x17C bit 53
    // accord, crv: 0x1BE bit 4
    bool is_user_brake_msg = honda_alt_brake_msg ? ((addr) == 0x1BE) : ((addr) == 0x17C);
    if (is_user_brake_msg) {
      brake_pressed = honda_alt_brake_msg ? (GET_BYTE((to_push), 0) & 0x10) : (GET_BYTE((to_push), 6) & 0x20);
    }

    // length check because bosch hardware also uses this id (0x201 w/ len = 8)
    if ((addr == 0x201) && (len == 6)) {
      gas_interceptor_detected = 1;
      int gas_interceptor = HONDA_GET_INTERCEPTOR(to_push);
      gas_pressed = gas_interceptor > HONDA_GAS_INTERCEPTOR_THRESHOLD;
      gas_interceptor_prev = gas_interceptor;
    }

    if (!gas_interceptor_detected) {
      if (addr == 0x17C) {
        gas_pressed = GET_BYTE(to_push, 0) != 0;
      }
    }

    // disable stock Honda AEB in unsafe mode
    if ( !(unsafe_mode & UNSAFE_DISABLE_STOCK_AEB) ) {
      if ((bus == 2) && (addr == 0x1FA)) {
        bool honda_stock_aeb = GET_BYTE(to_push, 3) & 0x20;
        int honda_stock_brake = (GET_BYTE(to_push, 0) << 2) + ((GET_BYTE(to_push, 1) >> 6) & 0x3);

        // Forward AEB when stock braking is higher than openpilot braking
        // only stop forwarding when AEB event is over
        if (!honda_stock_aeb) {
          honda_fwd_brake = false;
        } else if (honda_stock_brake >= honda_brake) {
          honda_fwd_brake = true;
        } else {
          // Leave Honda forward brake as is
        }
      }
    }

    // if steering controls messages are received on the destination bus, it's an indication
    // that the relay might be malfunctioning
    bool stock_ecu_detected = false;
    int bus_rdr_car = (honda_hw == HONDA_BH_HW) ? 0 : 2;  // radar bus, car side
    if ((safety_mode_cnt > RELAY_TRNS_TIMEOUT) && ((addr == 0xE4) || (addr == 0x194))) {
      if (((honda_hw != HONDA_N_HW) && (bus == bus_rdr_car)) ||
        ((honda_hw == HONDA_N_HW) && (bus == 0))) {
        stock_ecu_detected = true;
      }
    }
    generic_rx_checks(stock_ecu_detected);
  }
  return valid;
}

// all commands: gas, brake and steering
// if controls_allowed and no pedals pressed
//     allow all commands up to limit
// else
//     block all commands that produce actuation

static int honda_tx_hook(CAN_FIFOMailBox_TypeDef *to_send) {

  int tx = 1;
  int addr = GET_ADDR(to_send);
  int bus = GET_BUS(to_send);

  if ((honda_hw == HONDA_BG_HW) && !honda_bosch_long) {
    tx = msg_allowed(to_send, HONDA_BG_TX_MSGS, sizeof(HONDA_BG_TX_MSGS)/sizeof(HONDA_BG_TX_MSGS[0]));
  } else if ((honda_hw == HONDA_BG_HW) && honda_bosch_long) {
    tx = msg_allowed(to_send, HONDA_BG_LONG_TX_MSGS, sizeof(HONDA_BG_LONG_TX_MSGS)/sizeof(HONDA_BG_LONG_TX_MSGS[0]));
  } else if ((honda_hw == HONDA_BH_HW) && !honda_bosch_long) {
    tx = msg_allowed(to_send, HONDA_BH_TX_MSGS, sizeof(HONDA_BH_TX_MSGS)/sizeof(HONDA_BH_TX_MSGS[0]));
  } else if ((honda_hw == HONDA_BH_HW) && honda_bosch_long) {
    tx = msg_allowed(to_send, HONDA_BH_LONG_TX_MSGS, sizeof(HONDA_BH_LONG_TX_MSGS)/sizeof(HONDA_BH_LONG_TX_MSGS[0]));
  } else {
    tx = msg_allowed(to_send, HONDA_N_TX_MSGS, sizeof(HONDA_N_TX_MSGS)/sizeof(HONDA_N_TX_MSGS[0]));
  }

  if (relay_malfunction) {
    tx = 0;
  }

  // disallow actuator commands if gas or brake (with vehicle moving) are pressed
  // and the the latching controls_allowed flag is True
  int pedal_pressed = brake_pressed_prev && vehicle_moving;
  bool unsafe_allow_gas = unsafe_mode & UNSAFE_DISABLE_DISENGAGE_ON_GAS;
  if (!unsafe_allow_gas) {
    pedal_pressed = pedal_pressed || gas_pressed_prev || (gas_interceptor_prev > HONDA_GAS_INTERCEPTOR_THRESHOLD);
  }
  bool current_controls_allowed = controls_allowed && !(pedal_pressed);
  int bus_pt = (honda_hw == HONDA_BH_HW)? 1 : 0;

  // BRAKE: safety check (nidec)
  if ((addr == 0x1FA) && (bus == bus_pt)) {
    honda_brake = (GET_BYTE(to_send, 0) << 2) + ((GET_BYTE(to_send, 1) >> 6) & 0x3);
    if (!current_controls_allowed) {
      if (honda_brake != 0) {
        tx = 0;
      }
    }
    if (honda_brake > 255) {
      tx = 0;
    }
    if (honda_fwd_brake) {
      tx = 0;
    }
  }

  // BRAKE/GAS: safety check (bosch)
  if ((addr == 0x1DF) && (bus == bus_pt)) {
    int accel = (GET_BYTE(to_send, 3) << 3) | ((GET_BYTE(to_send, 4) >> 5) & 0x7);
    accel = to_signed(accel, 11);
    if (!current_controls_allowed) {
      if (accel != 0) {
        tx = 0;
      }
    }
    if (accel < HONDA_BOSCH_ACCEL_MIN) {
      tx = 0;
    }

    int gas = (GET_BYTE(to_send, 0) << 8) | GET_BYTE(to_send, 1);
    gas = to_signed(gas, 16);
    if (!current_controls_allowed) {
      if (gas != HONDA_BOSCH_NO_GAS_VALUE) {
        tx = 0;
      }
    }
    if (gas > HONDA_BOSCH_GAS_MAX) {
      tx = 0;
    }
  }

  // STEER: safety check
  if ((addr == 0xE4) || (addr == 0x194)) {
    if (!current_controls_allowed) {
      bool steer_applied = GET_BYTE(to_send, 0) | GET_BYTE(to_send, 1);
      if (steer_applied) {
        tx = 0;
      }
    }
  }

    // Bosch supplemental control check
  if (addr == 0xE5) {
    if ((GET_BYTES_04(to_send) != 0x10800004) || ((GET_BYTES_48(to_send) & 0x00FFFFFF) != 0x0)) {
      tx = 0;
    }
  }

  // GAS: safety check (interceptor)
  if (addr == 0x200) {
    if (!current_controls_allowed) {
      if (GET_BYTE(to_send, 0) || GET_BYTE(to_send, 1)) {
        tx = 0;
      }
    }
  }

  // FORCE CANCEL: safety check only relevant when spamming the cancel button in Bosch HW
  // ensuring that only the cancel button press is sent (VAL 2) when controls are off.
  // This avoids unintended engagements while still allowing resume spam
  if ((addr == 0x296) && !current_controls_allowed && (bus == bus_pt)) {
    if (((GET_BYTE(to_send, 0) >> 5) & 0x7) != 2) {
      tx = 0;
    }
  }

  // 1 allows the message through
  return tx;
}

static void honda_nidec_init(int16_t param) {
  UNUSED(param);
  controls_allowed = false;
  relay_malfunction_reset();
  gas_interceptor_detected = 0;
  honda_hw = HONDA_N_HW;
  honda_alt_brake_msg = false;
  honda_bosch_long = false;
}

static void honda_bosch_giraffe_init(int16_t param) {
  controls_allowed = false;
  relay_malfunction_reset();
  honda_hw = HONDA_BG_HW;
  // Checking for alternate brake override from safety parameter
  honda_alt_brake_msg = GET_FLAG(param, HONDA_PARAM_ALT_BRAKE);
  // radar disabled so allow gas/brakes
  honda_bosch_long = GET_FLAG(param, HONDA_PARAM_BOSCH_LONG);
}

static void honda_bosch_harness_init(int16_t param) {
  controls_allowed = false;
  relay_malfunction_reset();
  honda_hw = HONDA_BH_HW;
  // Checking for alternate brake override from safety parameter
  honda_alt_brake_msg = GET_FLAG(param, HONDA_PARAM_ALT_BRAKE);
  // radar disabled so allow gas/brakes
  honda_bosch_long = GET_FLAG(param, HONDA_PARAM_BOSCH_LONG);
}

static int honda_nidec_fwd_hook(int bus_num, CAN_FIFOMailBox_TypeDef *to_fwd) {
  // fwd from car to camera. also fwd certain msgs from camera to car
  // 0xE4 is steering on all cars except CRV and RDX, 0x194 for CRV and RDX,
  // 0x1FA is brake control, 0x30C is acc hud, 0x33D is lkas hud,
  int bus_fwd = -1;

  if (!relay_malfunction) {
    if (bus_num == 0) {
      bus_fwd = 2;
    }
    if (bus_num == 2) {
      // block stock lkas messages and stock acc messages (if OP is doing ACC)
      int addr = GET_ADDR(to_fwd);
      bool is_lkas_msg = (addr == 0xE4) || (addr == 0x194) || (addr == 0x33D);
      bool is_acc_hud_msg = addr == 0x30C;
      bool is_brake_msg = addr == 0x1FA;
      bool block_fwd = is_lkas_msg || is_acc_hud_msg || (is_brake_msg && !honda_fwd_brake);
      if (!block_fwd) {
        bus_fwd = 0;
      }
    }
  }
  return bus_fwd;
}

static int honda_bosch_fwd_hook(int bus_num, CAN_FIFOMailBox_TypeDef *to_fwd) {
  int bus_fwd = -1;
  int bus_rdr_cam = (honda_hw == HONDA_BH_HW) ? 2 : 1;  // radar bus, camera side
  int bus_rdr_car = (honda_hw == HONDA_BH_HW) ? 0 : 2;  // radar bus, car side

  if (!relay_malfunction) {
    if (bus_num == bus_rdr_car) {
      bus_fwd = bus_rdr_cam;
    }
    if (bus_num == bus_rdr_cam)  {
      int addr = GET_ADDR(to_fwd);
      int is_lkas_msg = (addr == 0xE4) || (addr == 0xE5) || (addr == 0x33D);
      if (!is_lkas_msg) {
        bus_fwd = bus_rdr_car;
      }
    }
  }
  return bus_fwd;
}

const safety_hooks honda_nidec_hooks = {
  .init = honda_nidec_init,
  .rx = honda_rx_hook,
  .tx = honda_tx_hook,
  .tx_lin = nooutput_tx_lin_hook,
  .fwd = honda_nidec_fwd_hook,
  .addr_check = honda_rx_checks,
  .addr_check_len = sizeof(honda_rx_checks) / sizeof(honda_rx_checks[0]),
};

const safety_hooks honda_bosch_giraffe_hooks = {
  .init = honda_bosch_giraffe_init,
  .rx = honda_rx_hook,
  .tx = honda_tx_hook,
  .tx_lin = nooutput_tx_lin_hook,
  .fwd = honda_bosch_fwd_hook,
  .addr_check = honda_rx_checks,
  .addr_check_len = sizeof(honda_rx_checks) / sizeof(honda_rx_checks[0]),
};

const safety_hooks honda_bosch_harness_hooks = {
  .init = honda_bosch_harness_init,
  .rx = honda_rx_hook,
  .tx = honda_tx_hook,
  .tx_lin = nooutput_tx_lin_hook,
  .fwd = honda_bosch_fwd_hook,
  .addr_check = honda_bh_rx_checks,
  .addr_check_len = sizeof(honda_bh_rx_checks) / sizeof(honda_bh_rx_checks[0]),
};
