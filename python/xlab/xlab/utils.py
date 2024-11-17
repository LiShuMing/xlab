
def get_content(filename):
    fp = open(filename, 'r')
    content = ' '.join(fp.readlines())
    fp.close()
    return content

def write_content(fn, content):
    fp = open(fn, 'w')
    fp.write(content)
    fp.close()