#include <iostream>

const uint32_t TOYOTA_PARAM_OFFSET = 8U;
const uint32_t TOYOTA_EPS_FACTOR = (1U << TOYOTA_PARAM_OFFSET) - 1U;
const uint32_t TOYOTA_PARAM_ALT_BRAKE = 1U << TOYOTA_PARAM_OFFSET;
const uint32_t TOYOTA_PARAM_STOCK_LONGITUDINAL = 2U << TOYOTA_PARAM_OFFSET;

int main(int argc, char* argv[]) {
  std::cout << TOYOTA_EPS_FACTOR << std::endl;
  std::cout << TOYOTA_PARAM_ALT_BRAKE << std::endl;
  std::cout << TOYOTA_PARAM_STOCK_LONGITUDINAL << std::endl;
  return 0;
}