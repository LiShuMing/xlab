#include "../include/fwd.h"

/**
 * Sort implementation
 */
class Sort {
public:
    Sort() {
    }

    void bubbleSort(vector<int>& nums) {
        int n = nums.size();
        for (int i = 0; i < n - 1; i++) {
            for (int j = 0; j < n - i - 1; j++) {
                if (nums[j] > nums[j + 1]) {
                    swap(nums[j], nums[j + 1]);
                }
            }
        }
    }

    void selectionSort(vector<int>& nums) {
        int n = nums.size();
        for (int i = 0; i < n - 1; i++) {
            int min_index = i;
            for (int j = i + 1; j < n; j++) {
                if (nums[j] < nums[min_index]) {
                    min_index = j;
                }
            }
            swap(nums[i], nums[min_index]);
        }
    }

    void insertionSort(vector<int>& nums) {
        int n = nums.size();
        for (int i = 1; i < n; i++) {
            int key = nums[i];
            int j = i - 1;
            while (j >= 0 && nums[j] > key) {
                nums[j + 1] = nums[j];
                j--;
            }
            nums[j + 1] = key;
        }
    }

    void mergeSort(vector<int>& nums) {
        int n = nums.size();
        if (n <= 1) return;
        int mid = n / 2;
        vector<int> left(nums.begin(), nums.begin() + mid);
        vector<int> right(nums.begin() + mid, nums.end());
        mergeSort(left);
        mergeSort(right);
        merge(left, right, nums);
    }

    void merge(vector<int>& left, vector<int>& right, vector<int>& nums) {
        int i = 0, j = 0, k = 0;
        while (i < left.size() && j < right.size()) {
            if (left[i] < right[j]) {
                nums[k++] = left[i++];
            } else {
                nums[k++] = right[j++];
            }
        }
        while (i < left.size()) {
            nums[k++] = left[i++];
        }
        while (j < right.size()) {
            nums[k++] = right[j++];
        }
    }

    void quickSort(vector<int>& nums) {
        int n = nums.size();
        if (n <= 1) return;
        quickSort(nums, 0, n - 1);
    }

    void quickSort(vector<int>& nums, int left, int right) {
        if (left >= right) return;
        int pivot = nums[right];
        int i = left, j = left;
        while (j < right) {
            if (nums[j] < pivot) {
                swap(nums[i], nums[j]);
                i++;
            }
            j++;
        }
        swap(nums[i], nums[right]);
        quickSort(nums, left, i - 1);
        quickSort(nums, i + 1, right);
    }
};
void test_sort(vector<int>& nums) {
    Sort sort;
    {
        auto input = nums;  
        sort.bubbleSort(input);
        cout << "bubbleSort: " << strJoin(input, " ") << endl;
    }
    {
        auto input = nums;
        sort.selectionSort(input);
        cout << "selectionSort: " << strJoin(input, " ") << endl;
    }
    {
        auto input = nums;
        sort.insertionSort(input);
        cout << "insertionSort: " << strJoin(input, " ") << endl;
    }
    {
        auto input = nums;
        sort.mergeSort(input);
        cout << "mergeSort: " << strJoin(input, " ") << endl;
    }
    {
        auto input = nums;
        sort.quickSort(input);
        cout << "quickSort: " << strJoin(input, " ") << endl;
    }
}
int main() {
    vector<int> nums = {3, 2, 1, 5, 6, 4};
    test_sort(nums);
    return 0;
}