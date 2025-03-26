import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

const mockData = [
  { name: "Users", value: 1200 },
  { name: "Orders", value: 500 },
  { name: "Revenue", value: 75000 },
];

const recentTransactions = [
  { id: "#001", user: "John Doe", amount: "$200", status: "Completed" },
  { id: "#002", user: "Jane Smith", amount: "$450", status: "Pending" },
  { id: "#003", user: "Alice Brown", amount: "$300", status: "Completed" },
];

const AdminDashboard = () => {
  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Admin Dashboard</h1>

      {/* Stats Overview */}
      <div className="grid grid-cols-3 gap-6">
        {mockData.map((item, index) => (
          <Card key={index} className="shadow-lg rounded-lg p-4">
            <CardHeader>
              <CardTitle>{item.name}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xl font-semibold">{item.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Charts Section */}
      <div className="bg-white p-4 shadow-lg rounded-lg">
        <h2 className="text-lg font-semibold mb-4">Performance Overview</h2>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={mockData}>
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="value" fill="#4F46E5" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Recent Transactions */}
      <div className="bg-white p-4 shadow-lg rounded-lg">
        <h2 className="text-lg font-semibold mb-4">Recent Transactions</h2>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>User</TableHead>
              <TableHead>Amount</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {recentTransactions.map((transaction) => (
              <TableRow key={transaction.id}>
                <TableCell>{transaction.id}</TableCell>
                <TableCell>{transaction.user}</TableCell>
                <TableCell>{transaction.amount}</TableCell>
                <TableCell>{transaction.status}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};

export default HomeAdminDashboard;
