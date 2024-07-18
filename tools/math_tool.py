import random
import math


# 生成随机数的分布符合正态分布，均值为3，方差为10，若为负数取相反数
def generate_normal_random(mean=3, variance=10):
    stddev = math.sqrt(variance)
    result = random.gauss(mean, stddev)
    return result if result > 0 else -result
