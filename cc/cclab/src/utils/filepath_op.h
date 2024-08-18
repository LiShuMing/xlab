#pragma once

#include <stdint.h>
#include <string>
#include <vector>

#include <dirent.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

namespace xlab {

class FilePathOp {
  public:
    /// return 0 if exist, -1 if not exist
    static int exist(const std::string &name);

    /// return 0 if exist, -1 if not exist
    static int is_dir(const std::string &pathname);

    /// return 0 if is absolute path, -1 if not
    static int is_abs_path(const std::string &name);

    /**
     * @param pathname             directory to walk
     * @param child_dirs           output parameter, subdirectories under the directory
     * @param child_files          ouput parameter, files under the directory
     * @param with_pathname_prefix whether to add the pathname prefix to the output
     * @return 0 if success, -1 if failed
     * This method only visits the first layer of directories, if you need to visit the contents of
     * subdirectories, you need to recursively call it.
     */
    static int walk_dir(const std::string &pathname, std::vector<std::string> &child_dirs /*out*/,
                        std::vector<std::string> &child_files /*out*/,
                        bool with_pathname_prefix = true);

    /// return 0 if success, -1 if failed
    static int mkdir_recursive(const std::string &pathname);

    /// return 0 if success, -1 if failed or file not exist
    static int rm_file(const std::string &name);

    /// return 0 if success, -1 if failed or directory not exist
    static int rmdir_recursive(const std::string &pathname);

    /// @return 0 if success, -1 if failed
    static int rename(const std::string &src, const std::string &dst);

    /// append=true, append content to the end of the file,
    /// append=false, overwrite the original file content
    /// 0 if success, -1 if failed
    static int write_file(const std::string &filename, const std::string &content,
                          bool append = false);

    /// append=true, append content to the end of the file,
    /// append=false, overwrite the original file content
    /// 0 if success, -1 if failed
    static int write_file(const std::string &filename, const char *content, size_t content_size,
                          bool append = false);

    /**
     * @NOTICE
     * For most files under the /proc directory, stat() does not return the file
     * size in the st_size field; instead the field is returned with the value 0.
     */
    static int64_t get_file_size(const std::string &filename);

    /**
     * 读文件，对get_file_size()+read_file()的封装，更易于使用
     * @return 成功返回文件内容，失败返回std::string()
     */
    static std::string read_file(const std::string &filename);

    /**
     * 由于/proc下面的文件无法通过::stat()获取文件长度，所以提供参数让调用者填入一个fixed长度
     */
    static std::string read_file(const std::string &filename, size_t content_size);

    /**
     * @param filename     文件名
     * @param content      传出参数，读取到的文件内容，内存由外部申请
     * @param content_size 最大读入大小
     *
     * @return 成功返回实际读入大小，失败返回-1
     *
     */
    static int64_t read_file(const std::string &filename, char *content /*out*/,
                             size_t content_size);

    /// @TODO 能否统一成一个接口，内部判断是否是否为link
    static std::string read_link(const std::string &filename, size_t content_size);

    /**
     * @param path     目录
     * @param filename 文件名
     *
     * 连接目录和文件名，解决`path`后面'/'和`filename`前面'/'是否存在，重复的问题
     *
     */
    static std::string join(const std::string &path, const std::string &filename);

  private:
    FilePathOp();
    FilePathOp(const FilePathOp &);
    FilePathOp &operator=(const FilePathOp &);

}; // class FilePathOp

} // namespace xlab

namespace xlab {

#define IF_ZERO_RETURN_NAGETIVE_ONE(x)                                                             \
    do {                                                                                           \
        if ((x) == 0)                                                                              \
            return -1;                                                                             \
    } while (0);
#define IF_NULL_RETURN_NAGETIVE_ONE(x)                                                             \
    do {                                                                                           \
        if ((x) == NULL)                                                                           \
            return -1;                                                                             \
    } while (0);
#define IF_STRING_EMPTY_RETURN_NAGETIVE_ONE(x)                                                     \
    do {                                                                                           \
        if (x.empty())                                                                             \
            return -1;                                                                             \
    } while (0);

inline int FilePathOp::exist(const std::string &name) {
    IF_STRING_EMPTY_RETURN_NAGETIVE_ONE(name);
    struct stat st;
    return stat(name.c_str(), &st);
}

inline int FilePathOp::is_dir(const std::string &pathname) {
    IF_STRING_EMPTY_RETURN_NAGETIVE_ONE(pathname);
    struct stat st;
    if (stat(pathname.c_str(), &st) == -1) {
        return -1;
    }
    return S_ISDIR(st.st_mode) ? 0 : -1;
}

inline int FilePathOp::is_abs_path(const std::string &name) {
    return !name.empty() && (name[0] == '/');
}

inline int FilePathOp::walk_dir(const std::string &pathname, std::vector<std::string> &child_dirs,
                                std::vector<std::string> &child_files, bool with_pathname_prefix) {
    if (is_dir(pathname) == -1) {
        return -1;
    }

    child_dirs.clear();
    child_files.clear();

    DIR *open_ret = ::opendir(pathname.c_str());
    IF_NULL_RETURN_NAGETIVE_ONE(open_ret);

    struct dirent entry;
    struct dirent *result = NULL;
    for (;;) {
        if (::readdir_r(open_ret, &entry, &result) != 0) {
            break;
        }
        if (result == NULL) {
            break;
        }
        char *name = result->d_name;
        if (strcmp(name, ".") == 0 || strcmp(name, "..") == 0) {
            continue;
        }
        std::string file_with_path = FilePathOp::join(pathname, name);
        if (FilePathOp::exist(file_with_path.c_str()) != 0) {
            fprintf(stderr, "%s:%d %s\n", __FUNCTION__, __LINE__, file_with_path.c_str());
            continue;
        }
        if (FilePathOp::is_dir(file_with_path.c_str()) == 0) {
            child_dirs.push_back(with_pathname_prefix ? file_with_path : name);
        } else {
            child_files.push_back(with_pathname_prefix ? file_with_path : name);
        }
    }

    if (open_ret) {
        ::closedir(open_ret);
    }

    return 0;
}

inline int FilePathOp::mkdir_recursive(const std::string &pathname) {
    IF_STRING_EMPTY_RETURN_NAGETIVE_ONE(pathname);
    char *path_dup = strdup(pathname.c_str());
    size_t len = strlen(path_dup);
    if (len == 0) {
        return -1;
    }
    size_t i = path_dup[0] == '/' ? 1 : 0;
    for (; i <= len; ++i) {
        if (path_dup[i] == '/' || path_dup[i] == '\0') {
            char ch = path_dup[i];
            path_dup[i] = '\0';
            if (::mkdir(path_dup, 0755) == -1 && errno != EEXIST) {
                free(path_dup);
                return -1;
            }
            path_dup[i] = ch;
        }
    }
    free(path_dup);
    return 0;
}

inline int FilePathOp::rm_file(const std::string &name) {
    IF_STRING_EMPTY_RETURN_NAGETIVE_ONE(name);
    if (exist(name) == -1) {
        return 0;
    }
    if (is_dir(name) == 0) {
        return -1;
    }
    if (::unlink(name.c_str()) == -1) {
        return -1;
    }
    return 0;
}

inline int FilePathOp::rmdir_recursive(const std::string &pathname) {
    IF_STRING_EMPTY_RETURN_NAGETIVE_ONE(pathname);
    if (exist(pathname) == -1) {
        return 0;
    }
    if (is_dir(pathname) == -1) {
        return -1;
    }

    DIR *open_ret = ::opendir(pathname.c_str());
    IF_NULL_RETURN_NAGETIVE_ONE(open_ret);

    struct dirent entry;
    struct dirent *result = NULL;
    int ret = 0;
    for (;;) {
        if (::readdir_r(open_ret, &entry, &result) != 0) {
            break;
        }
        if (result == NULL) {
            break;
        }
        char *name = result->d_name;
        if (strcmp(name, ".") == 0 || strcmp(name, "..") == 0) {
            continue;
        }
        std::string file_with_path = FilePathOp::join(pathname, name);
        if (FilePathOp::exist(file_with_path.c_str()) != 0) {
            fprintf(stderr, "%s:%d %s\n", __FUNCTION__, __LINE__, file_with_path.c_str());
            continue;
        }
        if (FilePathOp::is_dir(file_with_path.c_str()) == 0) {
            if (FilePathOp::rmdir_recursive(file_with_path.c_str()) != 0) {
                ret = -1;
            }
        } else {
            if (FilePathOp::rm_file(file_with_path.c_str()) != 0) {
                ret = -1;
            }
        }
    }

    if (open_ret) {
        ::closedir(open_ret);
    }

    return (::rmdir(pathname.c_str()) == 0 && ret == 0) ? 0 : -1;
}

inline int FilePathOp::rename(const std::string &src, const std::string &dst) {
    IF_STRING_EMPTY_RETURN_NAGETIVE_ONE(src);
    IF_STRING_EMPTY_RETURN_NAGETIVE_ONE(dst);
    return ::rename(src.c_str(), dst.c_str());
}

inline int FilePathOp::write_file(const std::string &filename, const char *content,
                                  size_t content_size, bool append) {
    IF_STRING_EMPTY_RETURN_NAGETIVE_ONE(filename);
    IF_NULL_RETURN_NAGETIVE_ONE(content);
    IF_ZERO_RETURN_NAGETIVE_ONE(content_size);
    FILE *fp = fopen(filename.c_str(), append ? "ab" : "wb");
    IF_NULL_RETURN_NAGETIVE_ONE(fp);
    size_t written = fwrite(reinterpret_cast<const void *>(content), 1, content_size, fp);
    fclose(fp);
    return (written == content_size) ? 0 : -1;
}

inline int FilePathOp::write_file(const std::string &filename, const std::string &content,
                                  bool append) {
    return FilePathOp::write_file(filename, content.c_str(), content.length(), append);
}

inline int64_t FilePathOp::get_file_size(const std::string &filename) {
    IF_STRING_EMPTY_RETURN_NAGETIVE_ONE(filename);
    if (exist(filename) == -1 || is_dir(filename) == 0) {
        return -1;
    }
    struct stat st;
    if (::stat(filename.c_str(), &st) == -1) {
        return -1;
    }
    return st.st_size;
}

inline int64_t FilePathOp::read_file(const std::string &filename, char *content,
                                     size_t content_size) {
    IF_STRING_EMPTY_RETURN_NAGETIVE_ONE(filename);
    IF_NULL_RETURN_NAGETIVE_ONE(content);
    IF_ZERO_RETURN_NAGETIVE_ONE(content_size);
    FILE *fp = fopen(filename.c_str(), "rb");
    IF_NULL_RETURN_NAGETIVE_ONE(fp);
    size_t read_size = fread(reinterpret_cast<void *>(content), 1, content_size, fp);
    fclose(fp);
    return read_size;
}

inline std::string FilePathOp::read_file(const std::string &filename) {
    int64_t size = get_file_size(filename);
    if (size <= 0) {
        return std::string();
    }
    return read_file(filename, size);
}

inline std::string FilePathOp::read_file(const std::string &filename, size_t content_size) {
    if (content_size == 0) {
        return std::string();
    }
    char *content = new char[content_size];
    int64_t read_size = read_file(filename.c_str(), content, content_size);
    if (read_size == -1) {
        delete[] content;
        return std::string();
    }
    std::string content_string(content, read_size);
    delete[] content;
    return content_string;
}

inline std::string FilePathOp::read_link(const std::string &filename, size_t content_size) {
    if (filename.empty() || content_size == 0) {
        return std::string();
    }
    char *content = new char[content_size];
    ssize_t length = ::readlink(filename.c_str(), content, content_size);
    if (length == -1) {
        delete[] content;
        return std::string();
    }
    std::string ret(content, length);
    delete[] content;
    return ret;
}

inline std::string FilePathOp::join(const std::string &path, const std::string &filename) {
    std::string ret;
    size_t path_length = path.length();
    size_t filename_length = filename.length();
    if (path_length == 0) {
        return filename;
    }
    if (filename_length == 0) {
        return path;
    }
    if (path[path_length - 1] == '/') {
        ret = path.substr(0, path_length - 1);
    } else {
        ret = path;
    }
    ret += "/";
    if (filename[0] == '/') {
        ret += filename.substr(1, filename_length - 1);
    } else {
        ret += filename;
    }
    return ret;
}

#undef IF_ZERO_RETURN_NAGETIVE_ONE
#undef IF_NULL_RETURN_NAGETIVE_ONE
#undef IF_STRING_EMPTY_RETURN_NAGETIVE_ONE

} // namespace xlab