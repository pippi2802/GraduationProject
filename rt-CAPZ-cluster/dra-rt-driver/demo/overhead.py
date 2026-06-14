import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

fontsize=14
fontsize_legend=14
fontsize_title=18
font_size_ticks = 11
data = pd.read_csv('overhead.csv')  # Replace 'your_file.csv' with your actual file name

# Convert columns to numeric, coercing errors
data['kubelet-plugin'] = pd.to_numeric(data['kubelet-plugin'], errors='coerce')
data['centralise-controller'] = pd.to_numeric(data['centralise-controller'], errors='coerce')

# Drop rows with NaN values caused by conversion errors
data = data.dropna()

# Calculate statistics for each column
for column in ['kubelet-plugin', 'centralise-controller']:
    max_value = data[column].max()
    min_value = data[column].min()
    average_value = data[column].mean()
    std_deviation = data[column].std()
    
    print(f"Statistics for {column}:")
    print(f"Maximum: {max_value}")
    print(f"Minimum: {min_value}")
    print(f"Average: {average_value}")
    print(f"Standard Deviation: {std_deviation}")
    print()

# Plot CDF and Histogram for each column


# # Plot CDF

# for column in ['kubelet-plugin', 'centralise-controller']:
#     sorted_data = np.sort(data[column].dropna())
#     yvals = np.arange(1, len(sorted_data) + 1) / float(len(sorted_data))
#     plt.plot(sorted_data, yvals, marker='.', linestyle='-', label=f"CDF of {column}")

# plt.xlabel('Response Time')
# plt.ylabel('Cumulative Probability')
# plt.title('CDF of Kubelet-Plugin and Centralised-Controller')
# plt.legend()
# plt.grid(True)

# Plot Histogram

plt.figure(figsize=(6, 4))
plt.hist(data["kubelet-plugin"], bins=15)

plt.xlabel('Time overhead (ms)',fontsize=fontsize)
plt.ylabel('Frequency',fontsize=fontsize)
# plt.title('Histogram of Kubelet-plugin',fontsize=fontsize_title)
plt.legend(fontsize=fontsize_legend)
plt.grid(True)

plt.tight_layout()
plt.savefig('overhead_kp.pdf') 

plt.figure(figsize=(6, 4))
plt.hist(data["centralise-controller"], bins=15)

plt.xlabel('Time overhead (ms)',fontsize=fontsize)
plt.ylabel('Frequency',fontsize=fontsize)
# plt.title('Histogram of Centralised-Controller',fontsize=fontsize_title)
plt.legend(fontsize=fontsize_legend)
plt.grid(True)

plt.tight_layout()
plt.savefig('overhead_cc.pdf') 
