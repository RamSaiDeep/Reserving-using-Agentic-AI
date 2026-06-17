import chainladder as cl
tri = cl.load_sample('comauto')
df = tri.to_frame()
print("Total Paid:", df['CumPaidLoss_D'].max())
