# coding=utf-8
import zlib


def compress_data(data):
    # 使用zlib压缩数据
    compressed_data = zlib.compress(data)
    return compressed_data


def decompress_data(compressed_data):
    # 使用zlib解压缩数据
    decompressed_data = zlib.decompress(compressed_data)
    return decompressed_data

if __name__ == '__main__':
    # 示例二进制数据
    binary_data = b"This is some binary data that we want to compress."

    # 压缩数据
    compressed = compress_data(binary_data)
    print("Compressed data size:", len(compressed))

    # 解压缩数据
    decompressed = decompress_data(compressed)
    print("Decompressed data:", decompressed)
